local P = class("IngameReplayEdit", UiDialog)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Center = self:find("Center", self.AnimRoot)

    self.EditInput = self:find("EditInput", self.Center)
    self.ConfirmButton = self:find("ConfirmButton", self.Center)
    self.ResetButton = self:find("ResetButton", self.Center)
    self.CloseButton = self:find("CloseButton", self.Center)

    bee.checkInputField(self.EditInput, _T("LAB_GAME_085"))

    bee.addClick(self.CloseButton, function()
        self:hideUI()
    end)
    bee.addClick(self.ConfirmButton, function()
        self:onClickConfirm()
    end)
    bee.addClick(self.ResetButton, function()
        self:onClickRecover()
    end)
end

function P:onStart()
    self._data = self._params.data -- {gameid, remark, title}
    self._scheme = self._params.scheme

    local Item1 = self:find("Item1", self.Center)
    bee.setText(self:find("TextName", Item1), GameModel:getReplayTitle(self._data))

    -- 预填已有备注
    if self._data.remark then
        bee.setText(self.EditInput, self._data.remark, "InputField")
    end
    
    local ImageCards = {
        self:find("Cardtype/Card1", Item1),
        self:find("Cardtype/Card2", Item1),
        self:find("Cardtype/Card3", Item1),
        self:find("Cardtype/Card4", Item1),
        self:find("Cardtype/Card5", Item1),
    }
    local d = tpl_card_back[DecorationModel:getCurCardBack(self._scheme)]
    for i = 1, 5 do
        if self._data.cards[i] and self._data.cards[i] > 0 then
            bee.setIcon(ImageCards[i], GF.getCardImageByCode(self._data.cards[i], self._scheme))
        else
            bee.setIcon(ImageCards[i], d.image)
        end
    end
    local TextCardType
    local Number, Win, Lose = self:find("Number", Item1), self:find("Win", Item1), self:find("Lose", Item1)
    Number:SetActive(0 == self._data.profit)
    Win:SetActive(self._data.profit > 0)
    Lose:SetActive(self._data.profit < 0)
    if self._data.profit >= 0 then
        TextCardType = self:find("Cardname/ingame_replay_card_type_01/TextCardType", Item1)
        self:find("Cardname/ingame_replay_card_type_01", Item1):SetActive(true)
        self:find("Cardname/ingame_replay_card_type_02", Item1):SetActive(false)
        bee.setText(self:find("TextNum", Win), "+" .. _N(self._data.profit))
    else
        TextCardType = self:find("Cardname/ingame_replay_card_type_02/TextCardType", Item1)
        self:find("Cardname/ingame_replay_card_type_01", Item1):SetActive(false)
        self:find("Cardname/ingame_replay_card_type_02", Item1):SetActive(true)
        bee.setText(self:find("TextNum", Lose), "-" .. _N(-self._data.profit))
    end
    if self._data.hand_type > 0 or self._data.hand_type < 0 then
        bee.setText(TextCardType, _T(POKER_TYPE_NAME[self._data.hand_type]))
    else
        local _, cardType = PKHelper.getHoldemType({self._data.cards[1], self._data.cards[2]}, {self._data.cards[3], self._data.cards[4], self._data.cards[5], self._data.cards[6], self._data.cards[7]})
        bee.setText(TextCardType, _T(cardType))
    end
end

function P:onClickConfirm()
    local markText = bee.getText(self.EditInput, "InputField")

    Net:post("/collCard/collRemark", {
        gameid = self._data.gameid,
        remark = markText,
    }, function(d)
        if 0 == d.code then
            self._data.remark = markText
            UiManager:showToast(_T("LAB_GAME_087"))
            bee.emit("evt_ReplayRemarkChanged", self._data.gameid, markText)
            self:hideUI()
        end
    end)
end

function P:onClickRecover()
    bee.setText(self.EditInput, "", "InputField")
end

return P