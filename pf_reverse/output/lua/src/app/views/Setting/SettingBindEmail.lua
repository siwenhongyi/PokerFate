local P = class("SettingBindEmail", require("app.views.Login.LoginBase"))

function P:onAwake()
    local Center = self:find("AnimRoot/Center")
    self.InputFieldName = self:find("InputFieldName", Center)
    self.InputFieldCode = self:find("InputFieldCode", Center)
    self.TipsText = self:find("TipsText", Center)
    self.ButtonCode = self:find("ButtonCode", Center)
    self.ButtonCode2 = self:find("ButtonCode2", Center)

    bee.addClick(self:find("ButtonClose", Center), function()
        bee.emit("evt_showRegister")
        self:hideUI()
    end)

    bee.addClick(self:find("ButtonConfirm", Center), function()
        self:onBtConfirm()
    end)
    -- bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
    --     self:hideUI()
    -- end, true)
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
        bee.setText(self.TipsText, "")
        
        LoginModel:catchEmailCaptcha(email, function(data)
            if not data then
                return
            end
            if data.code == 0 then
                UiManager:showToast(_T("LAB_SETTINGS_069"))
            elseif data.code == tpl_HttpCode.HTTP_ACCOUNT_REGISTERED.code then
                bee.setText(self.TipsText, _T("HTTP_ACCOUNT_REGISTERED"))
            elseif data.code == tpl_HttpCode.HTTP_ACCOUNT_NOT_FOUND.code then
                bee.setText(self.TipsText, _T("HTTP_ACCOUNT_NOT_FOUND"))
            end
        end, 2)
        return true
    end)

    self:initInputSeek(self.InputFieldName, true)
end

function P:onBtConfirm()
    local email = bee.getText(self.InputFieldName, "InputField")
    local code = bee.getText(self.InputFieldCode, "InputField")
    
    if email == "" then
        UiManager:showToast(_T("LAB_E_MAIL_TIP"))
        return
    elseif not GF.isValidEmail(email) then
        UiManager:showToast(_T("LAB_EMAIL_WRONG"))
        return
    end

    if code == "" then
        UiManager:showToast(_T("LAB_VERI_CODE_WRONG"))
        return
    end

    Game:playSound("ui_button_confirm")

    -- 邮箱验证
    Net:post("player/bindEmail", {
        email = email,
        captcha = code,
        step = EMAIL_REGISTER_STEP.CAPTCHA,
        lang = LanguageManager:getLanguage(),
    }, function(data)
        if data and data.code == 0 then
            -- 设置密码
            UiManager:showUI("LoginSetPasswordDialog", {clickCb = function(pw)
                Net:post("player/bindEmail", {
                    email = email,
                    captcha = code,
                    password = pw,
                    step = EMAIL_REGISTER_STEP.PASSWORD,
                    lang = LanguageManager:getLanguage(),
                }, function(data)
                    if data.code == 0 then
                        PlayerModel:setBindEmail(email)
                        UiManager:showToast(_T("LAB_SETTINGS_068"))
                        bee.emit("evt_refreshBindEmail")
                        self:hideUI()
                    end
                end)
            end, closeCb = function()
                -- UiManager:showUI("SettingBindEmail")
                self:hideUI()
            end})
            self:hideUI()
        end
    end)
end

