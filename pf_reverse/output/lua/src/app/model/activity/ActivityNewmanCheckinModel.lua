local P = class("ActivityNewmanCheckinModel", require("app.model.activity.ActivityBase"))

local PopUpView = {
    [1] = "ActivityNewmanCheckin_popup",
    [2] = "ActivityGalaSeasonCheckin_popup",
    [3] = "ActivitySchoolCheckin_popup",
}

function P:ctor(logic)
	self.saveData = {}
	P.super.ctor(self, ActivityId.ActivitySignIn, ActivityType.TimeLimit)

    self._checkinId = 0
    self._checkinDays = {}
end

function P:afterLogin()
    self._checkinId = 0
    self._checkinDays = {}
    self._inited = nil
end

-- 获取签到数据
function P:reqActivityData()
    if self._inited then
        return
    end
	Net:post("/activity/eventCheckInData", {t = 1}, function(data)
        self._inited = true
		if data.code ~= 0 then
			return
		end

        self._checkinId = data.id or 0
        self._checkinDays = {}
        if data.data then
            for k, v in pairs(data.data) do
                self._checkinDays[tonumber(k)] = v
            end
        end
        self:refreshReddot()
	end)
end

function P:reqCheckin(cb)
    Net:post("/activity/recEventCheckIn", {id = self._checkinId}, function(data)
        if data.code ~= 0 then
            return
        end

        for k, v in ipairs(self._checkinDays) do
            if v == 1 then
                self._checkinDays[k] = 2
            end
        end

        if data.item_list then
            bee.showUiTask("BackpackClaimResult", {items = data.item_list, title = "activity_reward_title_tw"}, POP_TAG.Reward, LOBBY_POP_PRIORITY.Reward)
        end

        bee.runTask(POP_TAG.Reward)
        self:refreshReddot()

        if cb then
            cb(data)
        end
    end)
end

function P:checkAutoPop()
    if not PopUpView[self._checkinId] then
        return
    end
    if self["_isAutoPop" .. PlayerModel:getUid()] then
        return
    end
    for _, v in ipairs(self._checkinDays) do
        if v == 1 then
            bee.showUiTask(PopUpView[self._checkinId], nil, nil, LOBBY_POP_PRIORITY.ActivityNewmanCheckin)
            break
        end
    end
end

function P:setIsAutoPop()
    self["_isAutoPop" .. PlayerModel:getUid()] = true
end

function P:isActivityOpen()
    local d = tpl_event_check_in[self._checkinId]
    if d then
        local ct = bee.getServerTime()
        if (ct >= d.time_start or PlayerModel:isEventWhite()) and ct <= d.time_end then
            return true
        end
    end
    return false
end

-- 获取累签奖励列表
function P:getCheckinId()
	return self._checkinId
end

function P:isCheckin(day)
	return self._checkinDays[day] ~= nil
end

function P:isCheckinReward(day)
    return self._checkinDays[day] == 1
end

function P:isCheckinRewarded(day)
    return self._checkinDays[day] == 2
end

function P:refreshReddot()
    local num = 0
    for _, v in ipairs(self._checkinDays) do
        if v == 1 then
            num = num + 1
        end
    end
    RedManager:addTagWithNum(num, RedTag.ActivityNewmanCheckin)
end

function P:getCheckinStatus(day)
    return self._checkinDays[day] or ActivityCheckInStatus.NotReach
end

function P:evt_serverTimeCrossDay()
	bee.once(math.random(1, 60), function()
        self:reqActivityData()
    end)
end

