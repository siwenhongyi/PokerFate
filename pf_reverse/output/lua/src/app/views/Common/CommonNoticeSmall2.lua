local P = class("CommonNoticeSmall2", UiDialog)

function P:onAwake()
    self._stopMaskClick = true
    
    self.AnimRoot = self:find("AnimRoot")
    self.Panel = self:find("Center/Panel", self.AnimRoot)

    self.TextTitle = self:find("TextTitle", self.Panel)
    self.TextTip = self:find("TextTip", self.Panel)
    self.ConfirmButton = self:find("ConfirmButton", self.Panel)
    self.CloseButton = self:find("CloseButton", self.Panel)

    bee.addClick2(self:find("common_panel_mask_70", self.AnimRoot), function()
        if not self._params.noClose then
            self:onBtCancel()
        end
    end)
end

function P:onStart()
    bee.addClick(self.CloseButton, function ()
        self:onBtCancel()
    end)
    bee.addClick(self.ConfirmButton, function ()
        self:onBtSure()
    end)
end

function P:onShow()
    if self._params.text then
        bee.setText(self.TextTip, self._params.text)
    end
	if self._params.title then
        bee.setText(self.TextTitle, self._params.title)
	else
        bee.setText(self.TextTitle, _T("LAB_TIP"))
    end

    if self._params.noClose then
        self.CloseButton:SetActive(false)
    end
    self:refreshButtonText()
end

function P:refreshButtonText(button)
    if self._params.sureStr then
        bee.setText(self:find("Text", self.ConfirmButton), self._params.sureStr)
    end
end

function P:onBtSure()
    if self._params.onSure then
        if self._params.onSure() then return end
    end
    self:hideUI()
end

function P:onBtCancel()
    if self._params.onCancel then
        if self._params.onCancel() then return end
    end
    self:hideUI()
end

