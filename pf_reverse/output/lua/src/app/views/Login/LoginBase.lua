local P = class("LoginBase", UiBase)

function P:initVerifyButton(ButtonCode, ButtonCode2, TipsText, clickCb)
    self.ButtonCode, self.ButtonCode2 = ButtonCode, ButtonCode2
    self.ButtonCode:SetActive(true)
    self.ButtonCode2:SetActive(false)

    if TipsText then
        bee.setText(TipsText, "")
    end

    local TextCode = self:find("TextCode", ButtonCode2)
    local dt = 0
    local vCode = ""
    bee.removeAllClick(self.ButtonCode)
    bee.addClick(self.ButtonCode, function()
        if TipsText then
            bee.setText(TipsText, "")
        end

        if dt > 0 then
            return
        end
        if not bee.checkCd("register_send_code", 1) then
            UiManager:showToast(_T("LAB_FREQUENT_OP"))
            return
        end

        -- local name = emailCb()
        -- print("==== gggggggggg", name, emailCb)
        -- if name == "" then
        --     if TipsText then
        --         bee.setText(TipsText, _T("LAB_E_MAIL_TIP"))
        --     else
        --         UiManager:showToast( _T("LAB_E_MAIL_TIP"))
        --     end
        --     return
        -- elseif not GF.isValidEmail(name) then
        --     if TipsText then
        --         bee.setText(TipsText, _T("LAB_EMAIL_WRONG"))
        --     else
        --         UiManager:showToast( _T("LAB_EMAIL_WRONG"))
        --     end
        --     return
        -- end
        local isValid = true
        if clickCb then
            isValid = clickCb()
        end

        if not isValid then
            return
        end
        
        -- LoginModel:catchEmailCaptcha(name, function(data)
        --     if not data or not TipsText then
        --         return
        --     end
        --     if data.code == tpl_HttpCode.HTTP_ACCOUNT_REGISTERED.code then
        --         bee.setText(TipsText, _T("HTTP_ACCOUNT_REGISTERED"))
        --     elseif data.code == tpl_HttpCode.HTTP_ACCOUNT_NOT_FOUND.code then
        --         bee.setText(TipsText, _T("HTTP_ACCOUNT_NOT_FOUND"))
        --     end
        -- end)

        dt = 60
        bee.setText(TextCode, dt .. "S")
        self.ButtonCode:SetActive(false)
        self.ButtonCode2:SetActive(true)
        self:repeatN(60, 1, function()
            dt = dt - 1
            if dt <= 0 then
                self.ButtonCode:SetActive(true)
                self.ButtonCode2:SetActive(false)
            else
                bee.setText(TextCode, dt .. "S")
            end
        end)
    end)
end

function P:disableButtonCode()
    local dt = 60
    local TextCode = self:find("TextCode", self.ButtonCode2)
    bee.setText(TextCode, dt .. "S")
    self.ButtonCode:SetActive(false)
    self.ButtonCode2:SetActive(true)
    self:repeatN(dt, 1, function()
        dt = dt - 1
        if dt <= 0 then
            self.ButtonCode:SetActive(true)
            self.ButtonCode2:SetActive(false)
        else
            bee.setText(TextCode, dt .. "S")
        end
    end)
end

function P:initInputSeek(input, isSeek)
    local _isSeek = isSeek
    bee.addClick(self:find("ButtonSeek", input), function()
        _isSeek = not _isSeek
        if _isSeek then
            bee.setIcon(self:find("ButtonSeek/Image", input), "Common[common_icon_eye_login_01]")
        else
            bee.setIcon(self:find("ButtonSeek/Image", input), "Common[common_icon_eye_login_02]")
        end
        self:setInputSeek(input, _isSeek)
    end)
end

function P:setInputSeek(input, isSeek)
    local field = input:GetComponent("InputField")
    if isSeek then
        field.contentType = CU.UI.InputField.ContentType.Standard
    else
        field.contentType = CU.UI.InputField.ContentType.Password
    end
    local text = field.text
    field.text = ""
    field.text = text
end

