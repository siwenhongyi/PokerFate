local P = class("LoginForgotDialog", require("app.views.Login.LoginBase"))

function P:onStart()
    local Center = self:find("AnimRoot/Center")
    self.Center = Center

    self.BgAccount = self:find("BgAccount", Center)
    self.BgInfo = self:find("BgInfo", Center)
    self.BgEmail = self:find("BgEmail", Center)
    self.BgVerify = self:find("BgVerify", Center)

    self.TextError = self:find("TextError", self.BgAccount)
    self.TextErrorEmail = self:find("TextError", self.BgEmail)
    self.TextErrorVerify = self:find("TextError", self.BgVerify)

    bee.addClick(self:find("Panel/CloseButton", Center), function()
        bee.emit("evt_showRegister")
        self:hideUI()
    end)

    self.BgAccount:SetActive(true)
    self.BgInfo:SetActive(false)
    self.BgEmail:SetActive(false)
    self.BgVerify:SetActive(false)

    bee.addClick(self:find("ButtonSearch", self.BgAccount), function()
        self:onClickSearch()
        bee.logEvent("login-email-password-recovery")
    end)

    bee.addClick(self:find("BgTip/ButtonCopy", self.BgAccount), function()
        CS.SdkHelper.copyText(_T("LAB_SERVICE_EMAIL"))
        UiManager:showToast(_T("LAB_COPY_SUC"))
    end)
    -- bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
    --     self:hideUI()
    -- end, true)
end

function P:getSecretUid(uid)
    local s = tostring(uid)
    local h = string.sub(s, 1, 3)
    local e = string.sub(s, -3, -1)
    return h .. "****" .. e
end

function P:getSecretEmail(email)
    local sp = string.split(email, "@")
    local h = string.sub(sp[1], 1, 3)
    return h .. "****@" .. (sp[2] or "")
end

function P:onClickSearch()
    local name = bee.getText(self:find("InputFieldName", self.BgAccount), "InputField")

    if name == "" then
        -- UiManager:showToast(_T("LAB_RECOVER_INFO"))
        bee.setText(self.TextError, _T("LAB_RECOVER_INFO"))
        return
    end

    LoginModel:forgotPassword(RETRIEVE_STEP.NAME, name, nil, nil, function(data)
        if data.code == 0 then
            if data.type == RETRIEVE_TYPE.EMAIL then
                self._email = name
                self:initVerifyLayer()
            else
                self._info = name
                self:initInfoLayer(data)
            end
        else
            local e = tpl_errorCode[data.code]
            if e then
                bee.setText(self.TextError, _T(e.id))
            end
        end
    end, true)
end

function P:initInfoLayer(data)
    self.BgAccount:SetActive(false)
    self.BgInfo:SetActive(true)
    self.BgEmail:SetActive(false)
    self.BgVerify:SetActive(false)

    bee.setText(self:find("TextName", self.BgInfo), data.nickname)
    bee.setText(self:find("TextUid", self.BgInfo), "UID:" .. data.uid)
    bee.setText(self:find("TextTip", self.BgInfo), _F("LAB_RECOVER_EMAIL", data.email))

    if data.avatar then
        local d = tpl_props[data.avatar]
        if d then
            bee.setIcon(self:find("Avatar/mask/ImageHead", self.BgInfo), d.icon)
        end
    end

    bee.addClick(self:find("ButtonOk", self.BgInfo), function()
        self:initEmailLayer(data)
    end)
end

function P:initEmailLayer(data)
    self.BgAccount:SetActive(false)
    self.BgInfo:SetActive(false)
    self.BgEmail:SetActive(true)
    self.BgVerify:SetActive(false)

    local sp = string.split(data.email, "@")
    local spPrefix = string.sub(sp[1], 1, 3)
    local spSuffix = "@" .. (sp[2] or "")
    bee.setText(self:find("TextAddr", self.BgEmail), spSuffix)
    bee.setText(self:find("InputFieldName", self.BgEmail), spPrefix,"InputField")

    bee.addClick(self:find("ButtonOk", self.BgEmail), function()
        local name = bee.getText(self:find("InputFieldName", self.BgEmail), "InputField")
        self._email = name .. spSuffix
        LoginModel:forgotPassword(RETRIEVE_STEP.CAPTCHA, self._info, string.replace(name, spPrefix, ""), nil, function(data)
            if data.code == 0 then
                self:initVerifyLayer()
            else
                local e = tpl_errorCode[data.code]
                if e then
                    bee.setText(self.TextErrorEmail, _T(e.id))
                end
            end
        end, true)
    end)
end

function P:initVerifyLayer()
    self.BgAccount:SetActive(false)
    self.BgInfo:SetActive(false)
    self.BgEmail:SetActive(false)
    self.BgVerify:SetActive(true)

    bee.setText(self:find("TextTip", self.BgVerify), _F("LAB_RECOVER_EMAIL", self._email))

    self:initVerifyButton(self:find("ButtonCode", self.BgVerify), self:find("ButtonCode2", self.BgVerify), nil, function()
        LoginModel:forgotPassword(RETRIEVE_STEP.NAME, self._email)
        return true
    end)
    self:disableButtonCode()

    bee.addClick(self:find("ButtonOk", self.BgVerify), function()
        local code = bee.getText(self:find("InputFieldCode", self.BgVerify), "InputField")

        if code == "" then
            -- UiManager:showToast(_T("LAB_VERI_CODE_WRONG"))
            bee.setText(self.TextErrorVerify, _T("LAB_VERI_CODE_WRONG"))
            return
        end

        LoginModel:forgotPassword(RETRIEVE_STEP.CAPTCHA, self._email, code, nil, function(data)
            if data.code == 0 then
                if data.type == RETRIEVE_TYPE.EMAIL then
                    bee.emit("evt_hideRegister")
                    self:evt_hideForgotCont()

                    -- 设置密码
                    UiManager:showUI("LoginSetPasswordDialog", {reset = true, closeCb = function()
                        bee.emit("evt_showForgotCont")
                    end, clickCb = function(pw)
                        LoginModel:forgotPassword(RETRIEVE_STEP.MODIFY, self._email, code, pw, function(data)
                            if data.code < 0 then
                                local e = tpl_errorCode[data.code]
                                if e then
                                    bee.setText(self.TextErrorVerify, _T(e.id))
                                end
                                return
                            end
                            UiManager:hideUI("LoginSetPasswordDialog")
                            bee.emit("evt_showRegister", {showLogin = true})
                            self:hideUI()
                        end)
                    end})
                end
            else
                local e = tpl_errorCode[data.code]
                if e then
                    bee.setText(self.TextErrorVerify, _T(e.id))
                end
            end
        end, true)
    end)
end

function P:evt_hideForgotCont()
    self.Center:SetActive(false)
end

function P:evt_showForgotCont()
    self.Center:SetActive(true)
end

function P:evt_lan_mod()
    if self._email then
        bee.setText(self:find("TextTip", self.BgVerify), _F("LAB_RECOVER_EMAIL", self._email))
    end
end

return P