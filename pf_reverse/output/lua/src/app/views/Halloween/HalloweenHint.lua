local P = class("HalloweenHint", UiDialog)

function P:onAwake()
    self.Pannel = self:find("AnimRoot/Center/Pannel")
    self.TextTitle = self:find("Title", self.Pannel)
    self.Text = self:find("Text", self.Pannel)
    self.RichText = self:find("RichText", self.Pannel)
    self.Tip = self:find("Tip", self.Pannel)
    self.ConfirmButton = self:find("ConfirmButton", self.Pannel)
    self.CancelButton = self:find("CancelButton", self.Pannel)
    self.CloseButton = self:find("CloseButton", self.Pannel)
    
    bee.addClick2(self.CloseButton, function()
        Game:playSound("ui_button_confirm")
        self:hideUI()
    end)

    bee.addClick(self.ConfirmButton, function ()
        self:onBtSure()
    end)
    bee.addClick(self.CancelButton, function ()
        self:onBtCancel()
    end)
end

function P:onShow()
    if not self._params then
        return
    end
    if self._params.text then
        bee.setText(self.Text, self._params.text)
    end
	if self._params.title then
        bee.setText(self.TextTitle, self._params.title)
	else
        bee.setText(self.TextTitle, _T("LAB_TIP"))
    end

    if self._params.richText then
        self.RichText:SetActive(true)
        bee.setText(self.Text, "")
        bee.setText(self.RichText, self._params.richText)
    end
    if self._params.tip then
        self.Tip:SetActive(true)
        bee.setText(self.Tip, self._params.tip)
    end

    self:refreshButtonText()
end

function P:refreshButtonText(button)
    if self._params.sureStr then
        bee.setText(self:find("Text", self.ConfirmButton), self._params.sureStr)
        -- self:setOrder(self.ConfirmButton)
    end
    if self._params.cancelStr then
        bee.setText(self:find("Text", self.CancelButton), self._params.cancelStr)
        -- self:setOrder(self.CancelButton)
    end
end

function P:onBtSure()
    if self._params.onSure then
        if self._params.onSure() then return end
    end
    self:hideUI()
end

function P:onBtCancel()
    self:hideUI()
end


return P