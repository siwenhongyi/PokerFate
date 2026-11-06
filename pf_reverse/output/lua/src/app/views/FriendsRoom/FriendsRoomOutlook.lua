local P = class("FriendsRoomOutlook", UiBase)

function P:onStart()
    local dt = GameModel.data:getOpenObserveStartTime() - bee.getServerTime()
    if dt < 0 then
        dt = 0
    end
    bee.once(dt, function()
        self:hideUIForce()
    end)

    if GameModel.data:isMTT() then
        bee.setText(self:find("AnimRoot/Center/panel/Text"), _F("LAB_TOURNAMENT_MTT_INFO67", tpl_constdata.Game_View_Delay))
    end
end

return P