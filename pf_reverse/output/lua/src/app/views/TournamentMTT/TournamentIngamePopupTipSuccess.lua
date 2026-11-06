local P = class("TournamentIngamePopupTipSuccess", UiBase)

function P:onAwake()
    self.LeftBottom = self:find("AnimRoot/LeftBottom")
    self.SuccessTip = self:find("Success", self.LeftBottom)

    bee.addClick(self:find("CloseButton", self.LeftBottom), function()
        self:hideUI()
    end)
end

function P:onShow()
    local data = GameModel.data
    
    if GameModel.data:isInObserve() then
        bee.setText(self:find("TextTip", self.SuccessTip), _T("LAB_TOURNAMENT_MTT_INFO65"))
    else
        bee.setText(self:find("TextTip", self.SuccessTip), _F("LAB_TOURNAMENT_MTT_INFO26", self._params.data.my_rank, self._params.data.reward_num))
    end
    
    -- self:once(2, function()
    --     self:hideUI()
    -- end)

    UiManager:hideUI("TournamentIngamePopupTipBubble")
    UiManager:hideUI("TournamentIngamePopupTipRest")
end

return P