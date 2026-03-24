local P = class("RankingModel", BaseModel)

function P:ctor()
    self.saveData = {
        cloud = {}
    }

    self._rankingList = {}

    P.super.ctor(self)
end

function P:afterLogin()
end

-- 排行榜是否可显示
function P:getRankingIsCanShow(id)
	local curTime = bee.getServerTime()
	local cfg = tpl_leaderboard_info[id]
	if cfg.time_open and cfg.time_end then
		if curTime < cfg.time_open or curTime >= (cfg.time_end + 604800) then
			return false
		end
	elseif cfg.time_open then
		if curTime < cfg.time_open then
			return false
		end
	elseif cfg.time_end then
		if curTime >= (cfg.time_end + 604800) then
			return false
		end
	end
	return true
end

-- 排行榜侧边栏列表（已排序）
function P:getRankingTabList()
	local list = {}
	local curTime = bee.getServerTime()
	for k,v in pairs(tpl_leaderboard_info) do
		if self:getRankingIsCanShow(v.id) then
			table.insert(list, v)
		end
	end
	table.sort(list, function(a, b) return a.index < b.index end)
	return list
end

-- 获取排行榜规则列表
function P:getRankingRuleList()
	local list = {}
	local curTime = bee.getServerTime()
	for k,v in pairs(tpl_leaderboard_rules) do
		if v.leaderboard_type then
			if self:getRankingIsCanShow(v.leaderboard_type) then
				table.insert(list, v)
			end
		else
			table.insert(list, v)
		end
	end
	table.sort(list, function(a, b) return a.index < b.index end)
	return list
end

-- 获取排行榜规则显示奖励列表
function P:getRuleRewardCfg(ruleId, rankId)
	local ruleCfg = tpl_leaderboard_rules[ruleId]
	local cfg = tpl_leaderboard_rewards
	if ruleCfg.change_time then
		if bee.getServerTime() < ruleCfg.change_time then
			cfg = tpl_leaderboard_rewards_old
		end
	end
	local list = {}
	for k,v in pairs(cfg) do
		if v.leaderboard_type == rankId then
			table.insert(list, v)
		end
	end
	table.sort( list, function(a, b) return a.id < b.id end)
	return list
end

-- 获取奖励列表
function P:getRewardCfg(id)
	local list = {}
	for k,v in pairs(tpl_leaderboard_rewards) do
		if v.leaderboard_type == id then
			table.insert(list, v)
		end
	end
	table.sort( list, function(a, b) return a.id < b.id end)
	return list
end

-- 请求排行榜数据
function P:requestRankingList(id, rankType, page, isImmediately)
	if not page then
		page = 1
	end
	local args = {}
	args.id = id
	args.skip = (page - 1) * 50
	args.size = 50
	args.last_week = rankType == RankingType.LastWeek
	args.immediately = isImmediately
    Net:post("activity/rankingList", args, function(data)
        if data.code ~= 0 then
            return
        end

        if not self._rankingList[id] then
        	self._rankingList[id] = {}
        end
        if not self._rankingList[id][rankType] then
        	self._rankingList[id][rankType] = {}
        	self._rankingList[id][rankType].list = {}
        end

        if page == 1 then
        	self._rankingList[id][rankType].list = {}
        end
        if data.list then
	        for k,v in pairs(data.list) do
	        	table.insert(self._rankingList[id][rankType].list, v)
	        end
	    end
	    if data.total then
	    	self._rankingList[id][rankType].total = data.total
	    end
	    if data.self then
        	self._rankingList[id][rankType].self = data.self
        end

        bee.emit("evt_rankingUpdate", {id = id, rankType = rankType})
    end)
end

-- 点赞请求
function P:requestLikeRanking(id, rank_id)
	local args = {}
	args.id = id
	args.rank_id = rank_id
    Net:post("activity/likeRanking", args, function(data)
        if data.code ~= 0 then
            return
        end

        for k, v in pairs(self:getRankingList(data.id, RankingType.CurWeek)) do
        	if v.rank_id == data.rank_id then
        		v.like = data.like
        		break
        	end
        end

        local selfData = self:getSelfRankData(data.id, RankingType.CurWeek)
        if selfData.rank_id == data.rank_id then
        	selfData.like = data.like
        end

        bee.emit("evt_rankingLikeUpdate", {id = data.id, rank_id = data.rank_id})
    end)
end

-- 获取排行榜数据
function P:getRankingList(id, rankType)
	if not self._rankingList[id] then
		return {}
	end
	if not self._rankingList[id][rankType] then
		return {}
	end
	return self._rankingList[id][rankType].list
end

-- 获取自己的排行榜数据
function P:getSelfRankData(id, rankType)
	if not self._rankingList[id] then
		return {}
	end
	if not self._rankingList[id][rankType] then
		return {}
	end
	return self._rankingList[id][rankType].self
end

function P:getRankingsListSize(id, rankType)
	if not self._rankingList[id] then
		return {}
	end
	if not self._rankingList[id][rankType] then
		return {}
	end
	return self._rankingList[id][rankType].total
end

-- 根据排行榜id获取排行榜数据
function P:getRankingDataById(id, rankType, rank_id)
	for k,v in pairs(self:getRankingList(id, rankType)) do
		if v.rank_id == rank_id then
			return v
		end
	end
	return {}
end

function P:getRankingType(id, rank)
	if not rank or rank == 0 then
		return -1
	end
	for i,v in ipairs(self:getRewardCfg(id)) do
		if v.ranking[2] then
			if rank >= v.ranking[1] and rank <= v.ranking[2] then
				return v.ranking_type
			end
		else
			if rank >= v.ranking[1] then
				return v.ranking_type
			end
		end
	end
end

-- 是否待关榜
function P:getIsWaitCloseRanking(id)
	local rankingCfg = tpl_leaderboard_info[id]
	if not rankingCfg.time_end then
		return false
	end
	return bee.getServerTime() >= rankingCfg.time_end
end

