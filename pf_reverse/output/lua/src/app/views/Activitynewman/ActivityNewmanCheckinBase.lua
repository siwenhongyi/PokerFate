local P = class("ActivityNewmanCheckinBase", UiBase)

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

    self.TextTime = self:find("activity_newman_checkin_bg_tcd/Time/TextTime")

    for k, v in ipairs(self._Items) do
        bee.addClick(v, function()
            self:onBtCheckin(k)
        end)
    end
end

function P:onStart()
    local data = tpl_event_check_in[ActivityNewmanCheckinModel:getCheckinId()] or tpl_event_check_in[1]

    for k, v in ipairs(self._Items) do
        local d = data["rewards"..k]
        local idx = 1
        for i = 1, #d - 1, 2 do
            local item = self:find("Item" .. idx, v)
            local d = {item_id = d[i], num = d[i + 1]}
            PropItem:bindItemNode(item, d)
            bee.addClick(item, function()
                if not self:onBtCheckin(k) then
                    Game:playSound("ui_button_confirm")
                    UiManager:showUI("CommonItemTip", {data = d, target = item})
                end
            end, true)
            idx = idx + 1
        end
    end

    bee.setText(self.TextTime, TimeHelp:getTimeLeftStr(data.time_end - bee.getServerTime()))
    self:schedule(1, function()
        bee.setText(self.TextTime, TimeHelp:getTimeLeftStr(data.time_end - bee.getServerTime()))
    end)
    self:refreshItems()
end

function P:onBtCheckin(day)
    if not ActivityNewmanCheckinModel:isActivityOpen() then
        UiManager:showToast(_T("LAB_EVENT_CHECK_IN_1"))
        bee.emit(EventDef.evt_activity_over, ActivityId.NewmanCheckin)
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
        if ActivityNewmanCheckinModel:isCheckinReward(k) then
            self:find("activity_newman_checkin_bg_xdb_01", v):SetActive(false)
            self:find("activity_newman_checkin_bg_xdb_02", v):SetActive(true)
        else
            self:find("activity_newman_checkin_bg_xdb_01", v):SetActive(true)
            self:find("activity_newman_checkin_bg_xdb_02", v):SetActive(false)
        end
        self:find("Mask", v):SetActive(ActivityNewmanCheckinModel:isCheckinRewarded(k))
    end
end

