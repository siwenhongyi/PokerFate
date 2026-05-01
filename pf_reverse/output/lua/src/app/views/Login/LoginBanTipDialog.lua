local P = class("LoginBanTipDialog", UiBase)

function P:onAwake()
    self.inPop = true
    local Panel = self:find("AnimRoot/Center/Panel")
    self.TextTip = self:find("TextTip", Panel)
    self.TextUID = self:find("TextUID", Panel)
    self.TextIP = self:find("TextIP", Panel)
    self.TextDeviceID = self:find("TextDeviceID", Panel)

    bee.addClick(self:find("CloseButton", Panel), function()
        self:hideUI()
    end)
    bee.addClick(self:find("ConfirmButton", Panel), function()
        self:hideUI()
    end)
    bee.addClick(self:find("Text/CopyButton", Panel), function()
        CS.SdkHelper.copyText(_T("LAB_SERVICE_EMAIL"))
        UiManager:showToast(_T("LAB_COPY_SUC"))
        bee.logEvent("login-bantip-csmailcopy")
    end)
end

function P:onShow()
    if self._params.err.id == "HTTP_IP_BLOCKED" then
        bee.setText(self.TextTip, _T("LAB_LOGIN_BAN_03"))
    elseif self._params.err.id == "HTTP_IMEI_BLOCKED" then
        bee.setText(self.TextTip, _T("LAB_LOGIN_BAN_02"))
    else
        bee.setText(self.TextTip, _T("LAB_LOGIN_BAN_01"))
    end

    bee.setText(self.TextUID, bee.getColorText(_T("LAB_SETTINGS_055"), '#60616E') .. (self._params.msg.uid or "--"))
    bee.setText(self.TextIP, bee.getColorText(_T("LAB_LOGIN_BAN_04"), '#60616E') .. (self._params.msg.login_ip or "--"))
    bee.setText(self.TextDeviceID, bee.getColorText(_T("LAB_EQUIPMENT_ID"), '#60616E') .. SdkHelper:getDeviceID())
end

return P