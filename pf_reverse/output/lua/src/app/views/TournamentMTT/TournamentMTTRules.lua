local P = class("TournamentMTTRules", UiFullView)

function P:onAwake()
    self.Center = self:find("AnimRoot/Center")
    self.RuleList = self:find("RuleList", self.Center)
    self.PageView = self.RuleList:GetComponent("PageView")
    self.ButtonLeft = self:find("ButtonLeft", self.Center)
    self.ButtonRight = self:find("ButtonRight", self.Center)

    self.Content = self:find("Viewport/Content", self.RuleList)

    self.VideoTip = self:find("AnimRoot/LeftTop/VideoTip")
    self.VideoTip:SetActive(false)

    bee.addClick(self:find("AnimRoot/RightTop/CloseButton"), function()
        self:hideUI()
    end)
    bee.addClick(self.VideoTip, function ()
        self:videoEvent()
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
    local s = self.Content.transform.sizeDelta
    s.y = self.node.transform.sizeDelta.y
    self.Content.transform.sizeDelta = s
    self.Content.transform.localPosition = bee.v3zero
    self:refreshUI()
end

function P:refreshUI()
    self.ButtonLeft:SetActive(self.PageView:GetCurIndex() > 0)
    self.ButtonRight:SetActive(self.PageView:GetCurIndex() < self.PageView:GetPageCount() - 1)
end

function P:evt_hideUiWhenAction(isVisible)
    self:onUiBlur(not isVisible, "evt_hideUiWhenAction", true)
end

function P:videoEvent()
    CU.Application.OpenURL("https://www.pokerfate.com/")
end

return P