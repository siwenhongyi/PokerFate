local P = class("TournamentIngameCount", UiBase)

function P:onAwake()
    self.Center = self:find("AnimRoot/Center")
    self.TextRank = self:find("TextRank", self.Center)
end

function P:onShow()
    if self._params and self._params.data then
        if self._params.data.my_rank == 0 then
            self.TextRank:SetActive(false)
        else
            self.TextRank:SetActive(true)
            bee.setText(self.TextRank, _F("LAB_TOURNAMENT_MTT_INFO53", self._params.data.my_rank, self._params.data.player_num))
        end
    end

    self:once(7, function()
        self:hideUI()
    end)
end

return P