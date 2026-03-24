local P = class("LoginRegisterDialog.lua", require("app.views.Login.LoginBase"))

function P:onAwake()
    local Panel = self:find("AnimRoot/Panel")
    self.InputFieldName = self:find("InputFieldName", Panel)
    self.InputFieldCode = self:find("InputFieldCode", Panel)
    self.TipsText = self:find("TipsText", Panel)
    self.ButtonCode = self:find("ButtonCode", Panel)
    self.ButtonCode2 = self:find("ButtonCode2", Panel)

    bee.addClick(self:find("ButtonClose", Panel), function()
        bee.emit("evt_showRegister")
        self:hideUI()
    end)

    bee.addClick(self:find("ButtonConfirm", Panel), function()
        self:onBtConfirm()
    end)
end

function P:onStart()
    bee.emit("evt_hideRegister")

    if self._params and self._params.email then
        bee.setText(self.InputFieldName, self._params.email, "InputField")
    end
    if self._params and self._params.captcha then
        bee.setText(self.InputFieldCode, self._params.captcha, "InputField")
    end

    self:initVerifyButton(self.ButtonCode, self.ButtonCode2, self.TipsText, function()
        local email = bee.getText(self.InputFieldName, "InputField")
        if not GF.isValidEmail(email) then
            bee.setText(self.TipsText, _T("LAB_EMAIL_WRONG"))
            return false
        end
        LoginModel:catchEmailCaptcha(email, function(data)
            if not data then
                return
            end
            
            if data.code and data.code ~= 0 then
                local e = tpl_errorCode[data.code]
                if e then
                    bee.setText(self.TipsText, _T(e.id))
                end
            end
        end, nil, true)
        return true
    end)

    self:initInputSeek(self.InputFieldName, true)
end

function P:onBtConfirm()
    local email = bee.getText(self.InputFieldName, "InputField")
    local code = bee.getText(self.InputFieldCode, "InputField")
    
    if email == "" then
        bee.setText(self.TipsText, _T("LAB_E_MAIL_TIP"))
        return
    elseif not GF.isValidEmail(email) then
        bee.setText(self.TipsText, _T("LAB_EMAIL_WRONG"))
        return
    end

    if code == "" then
        bee.setText(self.TipsText, _T("LAB_VERI_CODE_WRONG"))
        return
    end

    -- 邮箱验证
    LoginModel:emailRegister(email, code, nil, EMAIL_REGISTER_STEP.CAPTCHA, function(data)
        if data and data.code == 0 then
            -- 设置密码
            UiManager:showUI("LoginSetPasswordDialog", {clickCb = function(pw)
                UiManager:showLoadingMask("Register")
                LoginModel:emailRegister(email, code, pw, EMAIL_REGISTER_STEP.PASSWORD, function(data)
                    if data.code == 0 then
                        -- bee.emit("evt_showRegister", {showLogin = true})
                        -- UiManager:hideUI("LoginSetPasswordDialog")
                        -- 设置成功后登录游戏
                        UiManager:showLoadingMask("Login")
                        LoginModel:emailLogin(PlayerModel:getLoginEmail(), PlayerModel:getLoginPw())
                    else
                        bee.logEvent("login-email-login-failure", data.code)
                        local e = tpl_errorCode[data.code]
                        if e then
                            -- bee.setText(self.TipsText, _T(e.id))
                            -- UiManager:showToast(_T(e.id))
                        end
                    end
                    bee.emit("evt_showRegister")
                    UiManager:hideLoadingMask("Register")
                end)
            end})
            self:hideUI()
        else
            bee.logEvent("login-email-login-failure", data and data.code or -1)
            local e = tpl_errorCode[data.code]
            if e then
                bee.setText(self.TipsText, _T(e.id))
            end
        end
    end, true)
end

