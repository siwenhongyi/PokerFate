local P = class("CommonNoticeSmall", UiDialog)

function P:onAwake()
    self._stopMaskClick = true
    
    self.AnimRoot = self:find("AnimRoot")
    self.Notice = self:find("Center/Notice", self.AnimRoot)

    self.TextTitle = self:find("TextTitle", self.Notice)
    self.TextTip = self:find("TextTip", self.Notice)
    self.ConfirmButton1 = self:find("ConfirmButton1", self.Notice)
    self.ConfirmButton = self:find("ConfirmButton", self.Notice)
    self.CancelButton = self:find("CancelButton", self.Notice)
    self.CloseButton = self:find("CloseButton", self.Notice)
    self.BgNoTip = self:find("BgNoTip", self.Notice)
    self.TextTime = self:find("TextTime", self.Notice)

    if self.BgNoTip then
        self.TextNoTip = self:find("TextNoTip", self.BgNoTip)
    end
    self:refreshTimeText("")

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

    if self.BgNoTip then
        self.BgNoTip:SetActive(self._params.toggle ~= nil)
        if self.BgNoTip.activeSelf then
            bee.setCheck(self:find("ToggleCheck", self.BgNoTip), nil, self._params.toggle)
        end
    end
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

function P:setSureText(text)
    bee.setText(self:find("Text", self.ConfirmButton), text)
    bee.setText(self:find("Text", self.ConfirmButton1), text)
end

function P:refreshTimeText(str)
    if self.TextTime then
        bee.setText(self.TextTime, str)
    end
end

function P:onBtSure()
    if self._params.onSure then
        local isOn = nil
        if self.BgNoTip and self.BgNoTip.activeSelf then
            isOn = self:find("ToggleCheck", self.BgNoTip):GetComponent("Toggle").isOn
        end
        if self._params.onSure(isOn) then return end
    end
    self:hideUI()
end

function P:onBtCancel(isClose)
    if self._params.onCancel then
        if self._params.onCancel(isClose) then return end
    end
    self:hideUI()
end

function P:timeOut()
    self:hideUI()
end

return P