local P = class("SettingAccountRemove", UiBase)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Panel = self:find("Center/Panel", self.AnimRoot)

    self.Step1 = self:find("Step1", self.Panel)
    self.Step2 = self:find("Step2", self.Panel)
    self.Step3 = self:find("Step3", self.Panel)

    self.TextTip = self:find("TextTip", self.Step3)

    local Content = self:find("Detail/Viewport/Content", self.Step2)
    local TextInput = self:find("TextInput", Content)
    local InputFieldName = self:find("InputFieldName", Content)

    local CheckToggle = self:find("Check1Toggle", Content)
    bee.removeValueChanged(Check1Toggle)
    bee.addValueChanged(Check1Toggle, function()
        Game:playSound("ui_button_disabled")
    end)

    bee.addClick(self:find("TextTip", self.Step1), function()
        CU.Application.OpenURL(G_U_PP)
    end)
    bee.addClick(self:find("ConfirmButton", self.Step1), function()
        Game:playSound("ui_button_confirm")

        self.Step1:SetActive(false)
        self.Step2:SetActive(true)
        self.Step3:SetActive(false)

        if "" ~= PlayerModel:getBindEmail() then
            TextInput:SetActive(false)
            InputFieldName:SetActive(false)
        else
            TextInput:SetActive(true)
            InputFieldName:SetActive(true)
        end
    end)
    bee.addClick(self:find("CancelButton", self.Step1), function()
        self:hideUI()
    end)
    bee.addClick(self:find("CopyButton", self.Step1), function()
        CS.SdkHelper.copyText(_T("LAB_SERVICE_EMAIL"))
        UiManager:showToast(_T("LAB_COPY_SUC"))
    end)

    bee.addClick(self:find("ConfirmButton", self.Step2), function()
        local Check1Toggle = self:find("Check1Toggle", Content)

        local email = nil
        if InputFieldName.activeSelf then
            email = bee.getText(InputFieldName, "InputField")
            if "" == email or not GF.isValidEmail(email) then
                UiManager:showToast(_T("LAB_EMAIL_WRONG"))
                return
            end
        end
        if not bee.isCheck(Check1Toggle) then
            UiManager:showToast(_T("LAB_SETTINGS_067"))
            return
        end

        Game:playSound("ui_button_confirm")

        Net:post("player/deleteAccount", {
            email = email,
            lang = LanguageManager:getLanguage(),
            token = SdkHelper:getToken(),
            t = 1,
        }, function(data)
            if data.code ~= 0 then
                return
            end

            self.Step1:SetActive(false)
            self.Step2:SetActive(false)
            self.Step3:SetActive(true)
            self._isDelete = true

            bee.setText(self.TextTip, _F("LAB_SETTINGS_047", TimeHelp:getDateTimeStr(data.delete_time)))
            PlayerModel:setIsDeleted(true)
            bee.emit("evt_deleteAccount")
        end)

    end)
    bee.addClick(self:find("CancelButton", self.Step2), function()
        self:hideUI()
    end)

    bee.addClick(self:find("ConfirmButton", self.Step3), function()
        -- Game:quit()
        PlayerModel:setNotAutoLogin(true)
        PlayerModel:setIsLogin(false)
        PlayerModel:setAutoLogin(false)
        Net:sendReq("pb.UserLogoutREQ", {})
    end)
    bee.addClick(self:find("CancelButton", self.Step3), function()
        Net:post("player/cancelDeleteAccount", {
            t = 1,
            token = SdkHelper:getToken(),
        }, function(data)
            UiManager:showToast(_T("LAB_SETTINGS_109"))
            PlayerModel:setIsDeleted(false)
            bee.emit("evt_deleteAccount")
        end)
        self:hideUI()
    end)

    bee.addClick(self:find("CloseButton", self.Panel), function()
        if self._isDelete then
            PlayerModel:setNotAutoLogin(true)
            PlayerModel:setIsLogin(false)
            PlayerModel:setAutoLogin(false)
            Net:sendReq("pb.UserLogoutREQ", {})
        else
            self:hideUI()
        end
    end)
    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        self:hideUI()
    end, true)
end

function P:onShow()
    self.Step1:SetActive(true)
    self.Step2:SetActive(false)
    self.Step3:SetActive(false)
end

return P