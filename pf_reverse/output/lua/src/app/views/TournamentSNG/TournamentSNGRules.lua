local P = class("TournamentSNGRules", UiFullView)

function P:onAwake()
    self.Center = self:find("AnimRoot/Center")
    self.RuleList = self:find("RuleList", self.Center)
    self.PageView = self.RuleList:GetComponent("PageView")
    self.ButtonLeft = self:find("ButtonLeft", self.Center)
    self.ButtonRight = self:find("ButtonRight", self.Center)

    self.Content = self:find("Viewport/Content", self.RuleList)
    self.Chance = self:find("Chance", self.Content)
    self.League = self:find("League", self.Content)

    self.avatartitle_sng_01 = self:find("avatartitle_sng_01", self.League)

    bee.addClick(self:find("AnimRoot/RightTop/CloseButton"), function()
        self:hideUI()
    end)
    bee.addClick(self.ButtonLeft, function()
        Game:playSound("ui_button_confirm")
        if self.PageView:GetCurIndex() > 0 then
            self.PageView:PageTo(self.PageView:GetCurIndex() - 1);
            self:refreshUI()
        end
    end)
    bee.addClick(self.ButtonRight, function()
        Game:playSound("ui_button_confirm")
        if self.PageView:GetCurIndex() < self.PageView:GetPageCount() - 1 then
            self.PageView:PageTo(self.PageView:GetCurIndex() + 1);
            self:refreshUI()
        end
    end)
    self.PageView:OnPageChange(function()
        self:refreshUI()
    end)

    bee.addClick(self.avatartitle_sng_01, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonItemTip", {data = {id = 20403001}, target = self.avatartitle_sng_01})
    end)
    bee.addClick(self:find("Ticket1", self.League), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonItemTip", {data = {id = 11300001}, target = self:find("Ticket1", self.League)})
    end)
    bee.addClick(self:find("Ticket2", self.League), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonItemTip", {data = {id = 11300002}, target = self:find("Ticket2", self.League)})
    end)
    bee.addClick(self:find("Ticket3", self.League), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonItemTip", {data = {id = 11300003}, target = self:find("Ticket3", self.League)})
    end)
    bee.addClick(self:find("Ticket4", self.League), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonItemTip", {data = {id = 11300004}, target = self:find("Ticket4", self.League)})
    end)
end

function P:onShow()
    if self._params and self._params.data.byin_chips > 0 then
        self.League:SetActive(false)
        self.League.transform:SetParent(self.Center.transform, false)
    elseif self._params and self._params.data.byin_chips == 0 then
        self.Chance:SetActive(false)
        self.Chance.transform:SetParent(self.Center.transform, false)
    end
    local rateSum = 0
    for _, v in ipairs(tpl_sng_odds_list) do
        bee.setText(self:find("Multiple" .. v.id, self.Chance), v.multiple / 100)
        rateSum = rateSum + v.blast_probability
    end
    for _, v in ipairs(tpl_sng_odds_list) do
        bee.setText(self:find("Rate" .. v.id, self.Chance), tostring(v.blast_probability / rateSum * 100) .. "%")
    end

    local avatartitle_pos = {
        jp = bee.v3(564, -439),
        en = bee.v3(-450, -414),
        tw = bee.v3(179, -234),
        zh = bee.v3(144, -234),
        ko = bee.v3(144, -234),
    }
    self.avatartitle_sng_01.transform.localPosition = avatartitle_pos[LAN:getLanguage()] or avatartitle_pos["en"]

    self:refreshUI()
end

function P:refreshUI()
    self.ButtonLeft:SetActive(self.PageView:GetCurIndex() > 0)
    self.ButtonRight:SetActive(self.PageView:GetCurIndex() < self.PageView:GetPageCount() - 1)
end

function P:evt_hideUiWhenAction(isVisible)
    self:onUiBlur(not isVisible, "evt_hideUiWhenAction", true)
end

return P