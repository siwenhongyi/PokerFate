local P = class("HotSpringHallBlind", require("app.views.Lobby.OmahaBlinds"))

function P:onAwake()
    self._isMute = true
    self._gameType = GAME_GAME_TYPE.LOBBY_HOLDEM_ALLIN

    P.super.onAwake(self)

    self.TextCount = self:find("Ticket2/TextCount", self.RightTop)

    bee.addClick(self:find("Ticket2", self.RightTop), function()
        ItemModel:jumpViewByItemId(GPropId.Gold)
    end)
    bee.addClick(self:find("Ticket2/Icon", self.RightTop), function()
        UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(GPropId.Gold, true), target = self:find("Ticket2/Icon", self.RightTop)})
    end)
    
    bee.addClick(self:find("hotspring_btn_tips", self.LeftTop), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("HotSpringRule", {gameType = self._gameType})
        bee.logEvent("ingame-table-rules", self._gameType)
        bee.logEvent("onsen-rules_game")
    end, true)
end

function P:onShow()
    P.super.onShow(self)
    bee.setTextGold(self.TextCount, _N(PlayerModel:getGold()))
end

