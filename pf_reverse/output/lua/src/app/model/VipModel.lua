local P = class("VipModel", BaseModel)

function P:ctor()
    self.saveData = {}

    P.super.ctor(self)

    self._vip_level = 0
    self._vip_exp = 0
    self._claimed_level = {}    -- 已领取奖励的vip等级列表
end

function P:afterLogin()
    self._vip_level = 0
    self._vip_exp = 0
    self._claimed_level = {}    -- 已领取奖励的vip等级列表
end

function P:setVipLevel(level)
    self._vip_level = level
end

function P:getVipLevel()
    return self._vip_level
end

function P:setVipExp(exp)
    self._vip_exp = exp
end

function P:getVipExp()
    return self._vip_exp
end

function P:getMaxLevel()
    return tpl_vip_level_list[#tpl_vip_level_list].id
end

function P:isClaimedLevel(level)
    for _, v in ipairs(self._claimed_level) do
        if v == level then
            return true
        end
    end
    return false
end

function P:getCurData()
    return tpl_vip_level[self._vip_level] or tpl_vip_level_list[#tpl_vip_level_list]
end

-- 每日赠送次数
function P:getDailyGiftCounts()
    return self:getCurData().daily_gift_counts
end

-- 好友上限
function P:getFriendLimit()
    return self:getCurData().friend_limit
end

-- 黑名单上限
function P:getBlacklistLimit()
    return self:getCurData().blacklist_limit
end

-- 近期手牌展示上限
function P:getRecentHistoryLimit()
    return self:getCurData().recent_history_limit
end

-- 牌谱收藏上限
function P:getSheetLimit()
    return self:getCurData().sheet_limit
end

-- 装饰方案上限
function P:getPlanLimit()
    return self:getCurData().plan_limit
end

-- 每日增加经验手数
function P:getExpHands()
    return self:getCurData().exp_hands
end

-- 每日增加亲密度手数
function P:getFriendshipHands()
    return self:getCurData().friendship_hands
end

-- 等级经验加成 千分比
function P:getVipAdd()
    return self:getCurData().vip_add
end

-- 比赛经验场次
function P:getExpTournament()
    return self:getCurData().exp_tournament
end

-- 比赛好感度场次
function P:getFriendshipTournament()
    return self:getCurData().friendship_tournament
end

function P:refreshReddot()
    local num = 0
    for _, v in ipairs(tpl_vip_level_list) do
        if v.id <= self._vip_level and not self:isClaimedLevel(v.id) then
            num = num + 1
        end
    end
    RedManager:addTagWithNum(num, RedTag.VipClaimNum)
    ShopModel:refreshShopNewOutTag()
end

function P:reqVipData(cb)
	Net:post("vip/data", { t = 1 }, function(data)
		if data.code ~= 0 then
			return
		end
        
        self._vip_level = data.level
        self._vip_exp = data.exp
        self._claimed_level = data.claimed_level
        self:refreshReddot()
        if cb then
            cb()
        end
	end)
end

function P:reqVipReward(level, cb)
    for _, v in ipairs(self._claimed_level) do
        if v == level then
            UiManager:showToast(_T("LAB_VIP_TEXT_18"))
            return
        end
    end
	Net:post("vip/reward", {reward_level = level, cur_level = self._vip_level}, function(data)
		if data.code ~= 0 then
			return
		end

        table.insert(self._claimed_level, data.reward_level)
        self:refreshReddot()
        if cb then
            cb()
        end
	end)
end

return P