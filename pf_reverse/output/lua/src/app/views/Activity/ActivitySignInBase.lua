local P = class("ActivitySignInBase", UiBase)

function P:onAwake()
    local CheckIn = self:find("CheckIn")
    self._Items = {
        self:find("Item1", CheckIn),
        self:find("Item2", CheckIn),
        self:find("Item3", CheckIn),
        self:find("Item4", CheckIn),
        self:find("Item5", CheckIn),
        self:find("Item6", CheckIn),
        self:find("Item7", CheckIn),
    }

    self.TimeText = self:find("Time/TimeText")

    for k, v in ipairs(self._Items) do
        bee.addClick(v, function()
            self:onBtCheckin(k)
        end)
    end
end

function P:onStart()
    local data = tpl_event_check_in[ActivityNewmanCheckinModel:getCheckinId()] or tpl_event_check_in[1]

    for k, v in ipairs(self._Items) do
        -- 奖励
        local d = data["rewards"..k]
        local idx = 1
        for i = 1, #d - 1, 2 do
            local item = self:find("PropItem" .. idx, v)
            local d = {item_id = d[i], num = d[i + 1]}
            local prop = PropItem:create(item, d)
            bee.addClick(item, function()
                if ActivityNewmanCheckinModel:isCheckinReward(k) then
                    self:onBtCheckin(k)
                else
                    UiManager:showUI("CommonItemTip", {data = d, target = item})
                end
            end)
            idx = idx + 1
        end
        self:setItemIndex(v, k)
    end

    bee.setText(self.TimeText, TimeHelp:getTimeLeftStr(data.time_end - bee.getServerTime()))
    self:schedule(1, function()
        bee.setText(self.TimeText, TimeHelp:getTimeLeftStr(data.time_end - bee.getServerTime()))
    end)
    self:refreshItems()
end

-- 设置序号显示
function P:setItemIndex(item, index)
    bee.setText(self:find("Bg1/IndexText", item), "0" .. index)
    bee.setText(self:find("Bg2/IndexText", item), "0" .. index)
    bee.setText(self:find("Bg3/IndexText", item), "0" .. index)
end

function P:onBtCheckin(day)
    if not ActivityNewmanCheckinModel:isActivityOpen() then
        UiManager:showToast(_T("LAB_EVENT_CHECK_IN_1"))
        bee.emit(EventDef.evt_activity_over, ActivityId.ActivitySignIn)
        return
    end
    if ActivityNewmanCheckinModel:isCheckinReward(day) then
        ActivityNewmanCheckinModel:reqCheckin(function(data)
            if data.code ~= 0 then
                return
            end

            if bee.isNull(self.node) then
                return
            end
            self:refreshItems()
        end)
        return true
    end
end

function P:refreshItems()
    for k, v in ipairs(self._Items) do
        -- local isCurReward = ActivityNewmanCheckinModel:isCheckinReward(k)
        -- local isRewarded = ActivityNewmanCheckinModel:isCheckinRewarded(k)
        local checkInStatus = ActivityNewmanCheckinModel:getCheckinStatus(k)
        self:find("Bg1", v):SetActive(checkInStatus == ActivityCheckInStatus.Rewaraded)
        self:find("Bg2", v):SetActive(checkInStatus == ActivityCheckInStatus.NoReward)
        self:find("Bg3", v):SetActive(checkInStatus == ActivityCheckInStatus.NotReach)
        self:find("RewardedMask", v):SetActive(checkInStatus == ActivityCheckInStatus.Rewaraded)
    end
end

return P