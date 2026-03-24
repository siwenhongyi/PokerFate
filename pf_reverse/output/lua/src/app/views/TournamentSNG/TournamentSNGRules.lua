local P = class("TournamentSNGRules", UiBlurBase)

function P:onAwake()
    self.Center = self:find("AnimRoot/Center")
    self.RuleList = self:find("RuleList", self.Center)
    self.PageView = self.RuleList:GetComponent("PageView")
    self.ButtonLeft = self:find("ButtonLeft", self.Center)
    self.ButtonRight = self:find("ButtonRight", self.Center)

    self.Content = self:find("Viewport/Content", self.RuleList)
    self.Chance = self:find("Chance", self.Center)

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
end

function P:onShow()
    local rateSum = 0
    for _, v in ipairs(tpl_sng_odds_list) do
        bee.setText(self:find("Multiple" .. v.id, self.Chance), v.multiple)
        rateSum = rateSum + v.blast_probability
    end
    for _, v in ipairs(tpl_sng_odds_list) do
        bee.setText(self:find("Rate6" .. v.id, self.Chance), tostring(v.blast_probability / rateSum * 100) .. "%")
    end

    self:refreshUI()
end

function P:refreshUI()
    self.ButtonLeft:SetActive(self.PageView:GetCurIndex() > 0)
    self.ButtonRight:SetActive(self.PageView:GetCurIndex() < self.PageView:GetPageCount() - 1)
end

function P:evt_hideUiWhenAction(isVisible)
    self:onUiBlur(not isVisible, "evt_hideUiWhenAction", true)
end

