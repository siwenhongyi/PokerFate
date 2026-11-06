local P = class("TournamentIngamePopupTipBubble", UiBase)

function P:onAwake()
    self.LeftBottom = self:find("AnimRoot/LeftBottom")
    self.NoticeTip = self:find("Notice", self.LeftBottom)

    bee.addClick(self:find("CloseButton", self.LeftBottom), function()
        self:hideUI()
    end)
end

function P:onShow()
    local data = GameModel.data

    bee.setText(self:find("TextTip", self.NoticeTip), _F("LAB_TOURNAMENT_MTT_INFO22", self._params.data.reward_num + 1, self._params.data.reward_num))

    -- self:once(2, function()
    --     self:hideUI()
    -- end)

    UiManager:hideUI("TournamentIngamePopupTipRest")
    UiManager:hideUI("TournamentIngamePopupTipSuccess")
end

return P