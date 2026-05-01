local P = class("CommonNotice", UiDialog)

function P:onAwake()
    self._stopMaskClick = true
    
    self.AnimRoot = self:find("AnimRoot")
    self.Panel = self:find("Center/Panel", self.AnimRoot)

    self.TextTitle = self:find("TextTitle", self.Panel)
    self.TextTip = self:find("TextTip", self.Panel)
    self.ConfirmButton1 = self:find("ConfirmButton1", self.Panel)
    self.ConfirmButton = self:find("ConfirmButton", self.Panel)
    self.CancelButton = self:find("CancelButton", self.Panel)
    self.CloseButton = self:find("CloseButton", self.Panel)

    bee.addClick2(self:find("common_panel_mask_70", self.AnimRoot), function()
        if not self._params.noClose then
            self:onBtCancel()
        end
    end)
end

function P:onStart()
    bee.addClick(self.CloseButton, function ()
        self:onBtCancel(true)
    end)
    bee.addClick(self.ConfirmButton1, function ()
        self:onBtSure()
    end)
    bee.addClick(self.ConfirmButton, function ()
        self:onBtSure()
    end)
    bee.addClick(self.CancelButton, function ()
        self:onBtCancel()
    end)
end

function P:onShow()
    self._params = self._params or {}
    if self._params.text then
        bee.setText(self.TextTip, self._params.text)
    end
	if self._params.title then
        bee.setText(self.TextTitle, self._params.title)
	else
        bee.setText(self.TextTitle, _T("LAB_TIP"))
    end
    if self._params.button == 1 then
        self.ConfirmButton1:SetActive(true)
        self.ConfirmButton:SetActive(false)
        self.CancelButton:SetActive(false)
    else
        self.ConfirmButton1:SetActive(false)
        self.ConfirmButton:SetActive(true)
        self.CancelButton:SetActive(true)
    end

    if self._params.noClose then
        self.CloseButton:SetActive(false)
    end
    self:refreshButtonText()
end

function P:refreshButtonText(button)
    if self._params.sureStr then
        bee.setText(self:find("Text", self.ConfirmButton), self._params.sureStr)
        bee.setText(self:find("Text", self.ConfirmButton1), self._params.sureStr)
    end
    if self._params.cancelStr then
        bee.setText(self:find("Text", self.CancelButton), self._params.cancelStr)
    end
end

function P:onBtSure()
    if self._params.onSure then
        if self._params.onSure() then return end
    end
    self:hideUI()
end

function P:onBtCancel(isClose)
    if self._params.onCancel then
        if self._params.onCancel(isClose) then return end
    end
    self:hideUI()
end

return P