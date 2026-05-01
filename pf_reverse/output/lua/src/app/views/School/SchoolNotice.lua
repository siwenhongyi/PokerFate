local P = class("SchoolNotice", UiDialog)

function P:onAwake()
    self._stopMaskClick = true
    
    self.AnimRoot = self:find("AnimRoot")
    self.Notice = self:find("Center/Notice", self.AnimRoot)

    self.TextTitle = self:find("Popup/TextTitle", self.Notice)
    self.TextTip = self:find("TextTip", self.Notice)
    self.ConfirmButton = self:find("ConfirmButton", self.Notice)
    self.CancelButton = self:find("CancelButton", self.Notice)
    self.CloseButton = self:find("Popup/school_btn_tc_close", self.Notice)

    bee.addClick2(self:find("common_panel_mask_70", self.AnimRoot), function()
        if self._params.closeNoCancel then
            self:hideUI()
        elseif not self._params.noClose then
            self:onBtCancel()
        end
    end)
end

function P:onStart()
    bee.addClick(self.CloseButton, function ()
        if self._params.closeNoCancel then
            self:hideUI()
            return
        end
        self:onBtCancel()
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
    if self._params.cancelStr then
        bee.setText(self:find("Text", self.CancelButton), self._params.cancelStr)
    end
end

function P:setSureText(text)
    bee.setText(self:find("Text", self.ConfirmButton), text)
end

function P:onBtSure()
    if self._params.onSure then
        local isOn = nil
        if self._params.onSure(isOn) then return end
    end
    self:hideUI()
end

function P:onBtCancel()
    if self._params.onCancel then
        if self._params.onCancel() then return end
    end
    self:hideUI()
end

return P