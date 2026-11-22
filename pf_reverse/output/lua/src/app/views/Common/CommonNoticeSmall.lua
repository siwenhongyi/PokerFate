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

    self.RichTextTip = self:find("RichTextTip", self.Notice)
    self.SubTip = self:find("SubTip", self.Notice)

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

    if self._params.richText then
        self.RichTextTip:SetActive(true)
        bee.setText(self.TextTip, "")
        bee.setText(self.RichTextTip, self._params.richText)
    end
    if self._params.subText then
        self.SubTip:SetActive(true)
        bee.setText(self.SubTip, self._params.subText)
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
        self:setOrder(self.ConfirmButton)
    end
    if self._params.cancelStr then
        bee.setText(self:find("Text", self.CancelButton), self._params.cancelStr)
        self:setOrder(self.CancelButton)
    end
end

function P:setSureText(text)
    bee.setText(self:find("Text", self.ConfirmButton), text)
    bee.setText(self:find("Text", self.ConfirmButton1), text)
    self:setOrder(self.ConfirmButton)
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

function P:setOrder(btn)
    local btnText = self:find("Text", btn)
    local width = btnText:GetComponent("Text").preferredWidth
    if width < 250 then
        return
    end
    local icon = self:find("common_button_icon_yes", btn) or self:find("common_button_icon_no", btn)
    local dif = width - 250
    if icon then
        icon.transform.localPosition = icon.transform.localPosition - bee.v3(dif, 0, 0)
    end
    btnText.transform.localPosition = btnText.transform.localPosition - bee.v3(dif, 0, 0)
end

function P:onBtClose()
    self:onBtCancel()
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