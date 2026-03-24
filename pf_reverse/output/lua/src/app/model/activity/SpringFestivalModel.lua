
local P = class("SpringFestivalModel", require("app.model.activity.ActivityBase"))
SpringFestivalModel = P

function P:ctor()
	self.saveData = {}
	P.super.ctor(self, ActivityId.SpringFestival, ActivityType.TimeLimit)

    self._activeId = 0
    self._start_time = 0
    self._end_time = 0
    self._activeCfg = nil
    self._taskList = {}
    self._inited = false
end

function P:afterLogin()
    self._activeId = 0
    self._start_time = 0
    self._end_time = 0
    self._taskList = {}
    self._inited = false
end

function P:isActivityOpen()
    local ct = bee.getServerTime()
    if ct >= self._start_time and ct <= self._end_time then
    -- if ct <= self._end_time then
        return true
    end
    return false
end

-- 获取活动数据
function P:reqActivityData()
    if self._inited then
        return
    end
	Net:post("activity/festivalActivity", {t = 1}, function(data)
        self._inited = true
		if data.code ~= 0 then
			return
		end
        if data.data then
            self._activeId = data.data.id
            self._start_time = data.data.start_ts
            self._end_time = data.data.end_ts
            self._activeCfg = tpl_festival_activity[self._activeId]
            self:refreshReddot()
        end
        self:reqTaskList()
	end)
end

--开奖请求
function P:reqOpenRedPacket()
    Net:post("activity/festivalOpenPool", {id = self._activeId}, function(data)
        local code = data.code
        if code ~= 0 then
            if code == -800 then
                bee.emit("evt_springFestivalItemInsufficient")
            end
            return
        end

        if data.item_list then
            UiManager:showUI("BackpackClaimResult", {items = data.item_list, title = "common_result_title_tw", delay = 1.5}, POP_TAG.Reward, LOBBY_POP_PRIORITY.Reward)
            if data.is_publicity > 0 then
                bee.emit("evt_refreshBroadcast", data.item_list)
            end
        end
        
        self:refreshReddot()
        bee.logEvent("springfestival-open")
    end)
end

--获取广播内容
function P:reqBroadcastDatas()
    Net:post("activity/festivalRewardList", {id = self._activeId}, function(data)
        if data.code ~= 0 then
            return
        end
        bee.emit("evt_getBroadcastDatas", data.list)
    end)
end

--请求任务
function P:reqTaskList()
    Net:post("task/festivalTaskList", {id = self._activeId}, function(data)
        if data.code ~= 0 then
            return
        end
        self._taskList = data.list
        bee.emit("evt_refreshFestivalTaskList")
        self:refreshReddot()
    end)
end

--获取任务
function P:getTasks()
    return self._taskList or {}
end

--完成任务
function P:clearTasks(taskIds)
    Net:post("task/recReward", {id_arr = taskIds, task_cate = TaskCate.Festival}, function (data)
        if data.code ~= 0 then
            return
        end

        local rewards = {}
        if data.item_list then
			for k, v in pairs(data.item_list) do
				local isIn = false
				for k1, v1 in pairs(rewards) do
					if v1.item_id == v.item_id then
						v1.num = v.num + v1.num
						isIn = true
						break
					end
				end
				if not isIn then
					table.insert(rewards, v)
				end
			end
		end
        
		if next(rewards) then
			ShopModel:showRewardView(rewards, function()
				self:reqTaskList()
			end)
		end	
    end)
end

function P:refreshReddot()
    if self._activeCfg == nil then
        return
    end

    local taskCount = 0
    local tasks = self:getTasks()
    for _,v in pairs(tasks) do
        if v.status == TaskStatus.Completed then
            taskCount = taskCount + 1
        end
    end
    RedManager:addTagWithNum(taskCount, RedTag.SpringFestivalTask)

    local openCount = 0
    local itemCount = ItemModel:getItemNumById(GPropId.FestivalRedPacket)
    if itemCount >= self._activeCfg.cost[2] then
        openCount = openCount + 1
    end
    RedManager:addTagWithNum(openCount, RedTag.SpringFestivalRedPacket)

    RedManager:addTagWithNum(taskCount + openCount, RedTag.SpringFestival)
end

--获取表配置
function P:getActiveCfg()
    return self._activeCfg
end

--获取活动剩余时间
function P:getRemainTime(timeText, node)
    if self._activeId == 0 then
        return
    end
    local tag = nil
    local leftTime = self._end_time - bee.getServerTime()
    if leftTime > 0 then
        bee.setText(timeText, ShopModel:getShopTimeText(leftTime))
        tag = bee.schedule(1, function()
            leftTime = leftTime - 1
            if leftTime > 0 then
                bee.setText(timeText, ShopModel:getShopTimeText(leftTime))
            else
                bee.setText(timeText, _T("LAB_BACKPACK_DES_21"))
            end
        end, node)
    else
        bee.setText(timeText, _T("LAB_BACKPACK_DES_21"))
    end
    return tag
end

function P:evt_serverTimeCrossDay()
	bee.once(math.random(1, 60), function()
        self:reqTaskList()
    end)
end


