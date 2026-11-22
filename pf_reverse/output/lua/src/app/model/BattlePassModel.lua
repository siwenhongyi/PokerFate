local P = class("BattlePassModel", BaseModel)

function P:ctor()
    self.saveData = {}

    P.super.ctor(self)
end

function P:afterLogin()
	self._curLevel = nil
	self._battle_pass_id = nil
	self._weekly_list = nil
	self._period_list = nil
    self._loop_times_free = nil
    self._loop_times_paid = nil
    self._level_free_reward_ids = nil
    self._level_paid_reward_ids = nil
	self:reqBattlePassDetail()
end

function P:isOpenPass(checkId)
	if not checkId then
		checkId = self._battle_pass_id
	end
	if not checkId then
		return false
	end
	local cfg = tpl_battle_pass_info[checkId]
	if not cfg then
		return false
	end
	return bee.getServerTime() <= cfg.time_end
end

function P:getCurPassId()
	return self._battle_pass_id
end

function P:reqBattlePassDetail()
    Net:post("task/battlePassDetail", nil, function(data)
        if data.code ~= 0 then
            return
        end

        if not data.battle_pass_id then
        	return
        end
        if not tpl_battle_pass_info[data.battle_pass_id] then
        	return
        end

        if data.weekly_list then
        	self._weekly_list = TaskModel:filtrateTask(data.weekly_list, tpl_battle_pass_tasks_week)
        end
        if data.list then
        	self._period_list = TaskModel:filtrateTask(data.list, tpl_battle_pass_tasks_period)
        end

        self._battle_pass_id = data.battle_pass_id

        self._loop_times_free = data.loop_times_free
        self._loop_times_paid = data.loop_times_paid

        self._level_free_reward_ids = data.level_free_reward_ids or {}
        self._level_paid_reward_ids = data.level_paid_reward_ids or {}

        self:setCurBattlePassLevel()
        bee.emit("evt_updateBattlePass")
        self:refreshBattlePassRedTag()
    end)
end

-- 获取通行证等级配置
function P:getBattlePassLevelCfg()
	local list = {}
	for i, v in ipairs(tpl_battle_pass_level_list) do
		if v.battle_pass_id == self._battle_pass_id then
			table.insert(list, v)
		end
	end
	return list
end

function P:getBattlePassLevelDic()
	local list = {}
	for i, v in ipairs(tpl_battle_pass_level_list) do
		if v.battle_pass_id == self._battle_pass_id then
			list[v.id] = v
		end
	end
	return list
end

function P:isUnlockPass()
	return self:isBoughtPass(1) or self:isBoughtPass(2)
end

-- 通行证是否已满级
function P:getBattlePassMaxLevel()
	return #self:getBattlePassLevelCfg() - 1
end

-- 当前通行证经验值
function P:getBattlePassExp()
	return ItemModel:getItemNumById(GPropId.BattlePassExp)
end

function P:getCurPassLevelId()
	if not self:isOpenPass() then
		return 0
	end
	local curExp = self:getBattlePassExp()
	local levelCfg = self:getBattlePassLevelCfg()
	local levelCount = #levelCfg
	if curExp >= levelCfg[levelCount - 1].exp then
		return levelCfg[levelCount - 1].id
	end
	for i = #levelCfg - 1, 1, -1 do
		if levelCfg[i].exp <= curExp then
			return levelCfg[i].id
		end
	end
	return 0
end

-- 当前通行证等级
function P:getCurPassLevel()
	if not self:isOpenPass() then
		return 0
	end
	local id = self:getCurPassLevelId()
	if not tpl_battle_pass_level[id] then
		return 0
	end
	return tpl_battle_pass_level[id].level
end

function P:getFreeRewardIsClaim(id)
	for k, v in pairs(self._level_free_reward_ids) do
		if id == v then
			return true
		end
	end
	return false
end

function P:getPayRewardIsClaim(id)
	for k, v in pairs(self._level_paid_reward_ids) do
		if id == v then
			return true
		end
	end
	return false
end

-- 免费-等级奖励循环领取次数
function P:getClaimloopTimesFree()
	return self._loop_times_free or 0
end

-- 付费-等级奖励循环领取次数
function P:getClaimloopTimesPay()
	return self._loop_times_paid or 0
end

-- 获取通行证溢出经验
function P:getPassOverflowExp()
	local maxLevel = self:getBattlePassMaxLevel()
	local curExp = self:getBattlePassExp()
	local levelCfg = self:getBattlePassLevelCfg()
	return curExp - levelCfg[maxLevel].exp
end

function P:getPassCycleCount()
	local overflowExp = self:getPassOverflowExp()
	if overflowExp <= 0 then
		return 0
	end
	local levelCfg = self:getBattlePassLevelCfg()
	return math.floor(overflowExp / levelCfg[#levelCfg].exp)
end

-- 获取每周任务列表
function P:getPassWeeklyTaskList()
	if not self._weekly_list then
		return {}
	end
	return TaskModel:sortTaskList(self._weekly_list)
end

-- 获取每期任务列表
function P:getPassPeriodTaskList()
	if not self._period_list then
		return {}
	end
	return TaskModel:sortTaskList(self._period_list)
end

function P:isBoughtPass(level_type)
	local cfg = self:getPassShopCfg(level_type)
	if not cfg then
		return false
	end
	return ShopModel:getLimitGoodsBoughtCount(cfg.shop_type, cfg.id) >= 1
end

function P:getPassShopCfg(level_type)
	for k, v in pairs(tpl_shop_battle_pass) do
		if v.battle_pass_id == self:getCurPassId() and v.level_type == level_type then
			return v
		end
	end
end

function P:getTotalPaidRewards()
	local levelCfg = self:getBattlePassLevelCfg()
	local list = {}
	for k, v in pairs(levelCfg) do
		if v.level ~= -1 then
			for k1, v1 in pairs(ShopModel:getRewardsList(v.rewards_2)) do
				if not list[v1.id] then
					list[v1.id] = clone(v1)
					list[v1.id].typeSort = ItemModel:_getTypeSort(tpl_props[v1.id].type)
				else
					list[v1.id].num = list[v1.id].num + v1.num
				end
			end
		end
	end

	local showList = {}
	for k, v in pairs(list) do
		table.insert(showList, v)
	end
	table.sort(showList, function(a, b) return a.typeSort < b.typeSort end)
	return showList
end

function P:reqBattlePassClaimReward(t, id_arr)
	Net:post("task/battlePassClaimReward", {type = t, id_arr = id_arr}, function(data)
		if data.code ~= 0 then
			return
		end
		
		-- 领取奖励
		if t == 3 then
			-- 领取奖励界面
			ShopModel:showRewardView(data.item_list)
			-- 循环奖励配置
			local levelDic = self:getBattlePassLevelDic()
			for k,v in pairs(id_arr) do
				table.insert(self._level_free_reward_ids, v)
				if self:isUnlockPass() then
					table.insert(self._level_paid_reward_ids, v)
				end
				if levelDic[v].level == -1 then
					local cycleCount = self:getPassCycleCount()
					self._loop_times_free = cycleCount
					if self:isUnlockPass() then
						self._loop_times_paid = cycleCount
					end
				end
			end
		elseif t == 1 then
			for k,v in pairs(id_arr) do
				for k1, v1 in pairs(self._period_list) do
					if v == v1.id then
						v1.status = TaskStatus.Received
						break
					end
				end
			end
		elseif t == 2 then
			for k, v in pairs(id_arr) do
				for k1, v1 in pairs(self._weekly_list) do
					if v == v1.id then
						v1.status = TaskStatus.Received
						break
					end
				end
			end
		elseif t == 0 then
			self:reqBattlePassDetail()
		end
		bee.emit("evt_updateBattlePass")
		self:refreshBattlePassRedTag()
	end)
end

function P:reqBattlePassPurchaseLevel(count)
	Net:post("task/battlePassPurchaseLevel", {count = count}, function(data)
	end)
end

function P:setCurBattlePassLevel()
	self._curLevel = self:getCurPassLevel()
end

function P:activeBattlePass()
	self.saveData["active_battle_pass_" .. PlayerModel:getUid()] = self:getCurPassId()
	self:onSave()
end

function P:isShowActiveView()
	if not self.saveData["active_battle_pass_" .. PlayerModel:getUid()] then
		return true
	end
end

function P:evt_ItemChangeRSP()
	if not self:isOpenPass() then
		return
	end
	self:showLevelUp()
	self:refreshBattlePassRedTag()
end

function P:refreshBattlePassRedTag()
	if not self:isOpenPass() then
		return
	end
	-- 可领取奖励
	local levelCfg = self:getBattlePassLevelCfg()
	local curLevel = self:getCurPassLevel()
	local isUnlockPass = self:isUnlockPass()
	local rewardTag = false
	for k, v in ipairs(levelCfg) do
		if v.level ~= -1 and v.level <= curLevel then
			if not self:getFreeRewardIsClaim(v.id) then
				rewardTag = true
				break
			elseif isUnlockPass and not self:getPayRewardIsClaim(v.id) then
				rewardTag = true
				break
			end
		else
			break
		end
	end
	-- 循环奖励
	local cycleCount = self:getPassCycleCount()
	if cycleCount - self:getClaimloopTimesFree() > 0 then
		rewardTag = true
	elseif isUnlockPass and cycleCount - self:getClaimloopTimesPay() > 0 then
		rewardTag = true
	end
	if rewardTag then
		RedManager:addTag(RedTag.BattlePassReward)
	else
		RedManager:removeTag(RedTag.BattlePassReward)
	end

	-- 任务奖励
	local weeklyTag = false
	for k, v in pairs(self:getPassWeeklyTaskList()) do
		if v.status == TaskStatus.Completed then
			weeklyTag = true
			break
		end
	end
	if weeklyTag then
		RedManager:addTag(RedTag.BattlePassWeekly)
	else
		RedManager:removeTag(RedTag.BattlePassWeekly)
	end
	local PeriodTag = false
	for k, v in pairs(self:getPassPeriodTaskList()) do
		if v.status == TaskStatus.Completed then
			PeriodTag = true
			break
		end
	end
	if PeriodTag then
		RedManager:addTag(RedTag.BattlePassPeriod)
	else
		RedManager:removeTag(RedTag.BattlePassPeriod)
	end
end

function P:evt_NoticeBRC(params)
    if params.type == tpl_PushConsts.PASSCARD_TASK_REFRESH.code then
        self:reqBattlePassDetail()
    elseif params.type == tpl_PushConsts.BATTLE_PASS_START.code then
    	self:reqBattlePassDetail()
    end
end

function P:showLevelUp()
	if not self:isOpenPass() then
		return
	end
	if not self._curLevel then
		return
	end

	if self._curLevel ~= self:getCurPassLevel() then
		bee.showUiTask("SpiritCatStyleLevelUp", nil, POP_TAG.Reward, LOBBY_POP_PRIORITY.PassUpgrade)
		bee.runTask(POP_TAG.Reward)
		self:setCurBattlePassLevel()
	end
end

function P:evt_pay_sucess(data)
	if not self:isOpenPass() then
		return
	end
    if data and data.pidData and 
    	(data.pidData.buy_id == self:getPassShopCfg(1).buy_id or
    	data.pidData.buy_id == self:getPassShopCfg(2).buy_id or
    	data.pidData.buy_id == self:getPassShopCfg(3).buy_id) then
    		
        bee.addTaskFunc(function()
        	bee.emit("evt_unlockBattlePass")
        	bee.runNextTask(POP_TAG.Reward)
    	end, 0, POP_TAG.Reward, LOBBY_POP_PRIORITY.BattlePassUnlock)
    	bee.runTask(POP_TAG.Reward)
    end
end

function P:initExp()
	self:refreshBattlePassRedTag()
	self:setCurBattlePassLevel()
end

return P