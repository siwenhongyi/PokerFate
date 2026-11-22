local P = class("MonopolyModel", require("app.model.activity.ActivityBase"))
MonopolyModel = P

function P:ctor()
    P.super.ctor(self, ActivityId.Monopoly, ActivityType.TimeLimit)

    self._start_time = 0
    self._end_time = 0

    self.activityId = 0
    self.activityItemId = 0
    self.multiple = 1
    self.totalConsume = 0
    self.rewardProgress = 0
    self.curPos = 1

    self.taskData = {}
    self.chessboardCfg = nil

    self.ctrling = false
end

function P:reqActivityData()
    self:getMonopolyInfo()
end

function P:isActivityOpen(subId)
    if not subId or subId == self:getAcitvityId() then
        if self._start_time > 0 then
            local ct = bee.getServerTime()
            if ct >= self._start_time and ct <= self._end_time then
                return true
            end
        end
    end
    return false
end

function P:getActivityEndTime()
    return self._end_time
end

--获取玩法信息
function P:getMonopolyInfo()
    Net:sendReq("pb.GetMonopolyActDataREQ", {}, function (msg)
        if msg.code ~= 0 then
            return
        end
        if msg.act_id == nil or msg.act_id == 0 then
            self.activityId = 0
            self._start_time = 0
            self._end_time = 0
            self.taskData = {}
            return
        end

        self.activityId = msg.act_id
        local cfg = tpl_monopoly_activity[self.activityId]
        if cfg then
            self.activityItemId = cfg.activity_item
        end

        self.multiple = LocalStore:getIntegerForKey("monopoly_multiple", 1)
        self.curPos = msg.index
        self.totalConsume = msg.all_cost_num or 0
        self.rewardProgress = msg.progress or 0

        self._start_time = cfg.time_start
        self._end_time = cfg.time_end
        if PlayerModel:isEventWhite() then
            self._start_time = cfg.white_list_start
            self._end_time = cfg.white_list_end
        end

        for _,v in pairs(tpl_monopoly_chessboard) do
            if v.activity_id == self.activityId then
                self.chessboardCfg = v
                break
            end
        end

        self:reqTaskList()
        --bee.emit("evt_MonopolyDataCallback")
    end)
end

--投掷色子
function P:playEvent()
    local multiple = self.multiple
    self.ctrling = true
    Net:sendReq("pb.ThrowDiceREQ", {multiple = multiple}, function (msg)
        self.ctrling = false
        if msg.code ~= 0 then
            bee.emit("evt_MonopolyPlayFail")
            return
        end

        self.curPos = msg.index
        self.totalConsume = msg.all_cost_num
        bee.emit("evt_MonopolyPlay", {multiple = multiple})
    end)
end

--获取进度奖励
function P:getProgressReward()
    Net:sendReq("pb.GetProgressRewardREQ", {})
end
function P:evt_GetProgressRewardRSP(msg)
    if msg.code ~= 0 then
        return
    end
    self.rewardProgress = msg.progress
    bee.emit("evt_MonopolyProgressReward")
end

--获取任务列表
function P:reqTaskList(cb)
    Net:post("task/monopolyTaskList", {}, function (data)
        if data.code ~= 0 then
			return
		end
        self.taskData = data.list or {}

        self:refreshReddot()
        if cb then
            cb()
        end
    end, function ()
        local taskView = UiManager:getUI("MonopolyTask")
        if taskView then
            UiManager:showToast(_T("LAB_NET_ERR_TIPS"))
        end
    end)
end

--领取任务奖励
function P:getTaskReward(id, cb, ids)
    local id_arr = ids or {id}
    Net:post("task/recMonopolyTaskRw", {id_arr = id_arr}, function (data)
        if data.code ~= 0 then
            return
        end

        for _, v in ipairs(self.taskData) do
            if table.indexof(id_arr, v.id) > 0 then
                v.status = TaskStatus.Received
            end
        end

        if cb then
            cb()
        end

        self:refreshReddot()

        if data.item_list then
            UiManager:showUI("BackpackClaimResult", {
                items = data.item_list
            })
        end
    end)
end

--玩法id
function P:getAcitvityId()
    return self.activityId
end

--道具数量
function P:getItemCount()
    if self.activityItemId > 0 then
        local item = ItemModel:getItem(self.activityItemId)
        return item and item.num or 0
    end
    return 0
end

--获取任务
function P:getTasks()
    return self.taskData or {}
end
function P:getTask(taskId)
    if self.taskData then
        for _, v in ipairs(self.taskData) do
            if v.task_id == taskId then
                return v
            end
        end
    end
    return nil
end

--设置倍率档位
function P:exchangeMultip()
    local multips, nums, cacheGears = self:getChessboardData()
    local itemCount = self:getItemCount()

    cacheGears = cacheGears + 1
    if multips[cacheGears] == nil then
        cacheGears = 1
    end
    if itemCount >= nums[cacheGears] then
        self.multiple = multips[cacheGears]
        LocalStore:setIntegerForKey("monopoly_multiple", self.multiple)
    else
        self.multiple = multips[1]
        LocalStore:setIntegerForKey("monopoly_multiple", self.multiple)
    end
end

--自动降档
function P:checkDownGearsMultip()
    local multips, nums, cacheGears = self:getChessboardData()
    local itemCount = self:getItemCount()
    if itemCount < nums[cacheGears] then
        local num = #multips
        for i = 1, num do
            cacheGears = cacheGears - 1
            if cacheGears == 0 then
                cacheGears = 1
                self.multiple = multips[cacheGears]
                LocalStore:setIntegerForKey("monopoly_multiple", self.multiple)
                return true
            end
            if itemCount >= nums[cacheGears] then
                self.multiple = multips[cacheGears]
                LocalStore:setIntegerForKey("monopoly_multiple", self.multiple)
                return true
            end
        end
    else
        return false
    end
end

--切档提示
function P:checkMultipTip()
    local multips, nums, cacheGears = self:getChessboardData()
    local itemCount = self:getItemCount()
    cacheGears = cacheGears + 1
    if nums[cacheGears] == nil then
        return nil
    end
    if itemCount >= nums[cacheGears] then
        return cacheGears
    end
end

--隐藏倍率切换按钮
function P:switchMultipleBtn()
    local minVal = self.chessboardCfg.param[3]
    local itemCount = self:getItemCount()
    return itemCount < minVal
end

--获取档位数据
function P:getChessboardData()
    local datas = self.chessboardCfg.param
    local dataCount = #datas / 2
    local multips = {} -- {datas[2], datas[4], datas[6]}
    local nums = {} -- {datas[1], datas[3], datas[5]}
    for i = 1, dataCount do
        table.insert(multips, datas[i * 2])
        table.insert(nums, datas[i * 2 - 1])
    end

    local gears = 1
    for k,v in pairs(multips) do
        if self.multiple == v then
            gears = k
            break
        end
    end
    return multips, nums, gears
end

function P:refreshReddot()
    local taskNum = 0
    for _, v in ipairs(self.taskData) do
        if v.status == TaskStatus.Completed then
            taskNum = taskNum + 1
        end
    end

    self.RewardCfgList = get_tpl_subKey(tpl_dice_consumption_rewards_list, "activity", self.activityId)
    table.sort(self.RewardCfgList, function (a, b) return a.id < b.id end)
    local rewardNum = 0
    for _,v in pairs(self.RewardCfgList) do
        if self.totalConsume >= v.quantity and v.id > self.rewardProgress then
            rewardNum = rewardNum + 1
        end
    end

    local itemCount = self:getItemCount()

    RedManager:addTagWithNum(taskNum, RedTag.MonopolyTask)
    RedManager:addTagWithNum(taskNum + rewardNum + itemCount, RedTag.Monopoly)
    
end

return P