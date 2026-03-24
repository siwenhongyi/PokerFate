local P = class("SettingTransferID", UiBase)

function P:onAwake()
    self.Panel = self:find("AnimRoot/Center/Panel")

    self.UnlinkButton = self:find("UnlinkButton", self.Panel)
    self.ConfirmButton = self:find("ConfirmButton", self.Panel)

    self.InputFieldPWD = self:find("InputFieldPWD", self.Panel)
    self.InputFieldPWD2 = self:find("InputFieldPWD2", self.Panel)
    self.InputFieldUID = self:find("InputFieldUID", self.Panel)

    self.TextPWD = self:find("TextPWD", self.Panel)
    self.TextUID = self:find("TextUID", self.Panel)
    self.TextTips = self:find("TextTips", self.Panel)
    self.TextTimeout = self:find("TextTimeout", self.Panel)
    self.CloseButton = self:find("CloseButton", self.Panel)
    self.TextTitle = self:find("TextTitle", self.Panel)

    bee.addClick(self.CloseButton, function()
        self:hideUI()
    end)
    bee.addClick(self.UnlinkButton, function()
        Game:playSound("ui_button_confirm")
        Net:post("/player/genAssocPwd", {assoc_pwd = ""}, function(data)
            bee.logEvent("login-account-transfer code-generate-cancel", 2)
            if 0 == data.code then
            end
            self:hideUI()
        end, nil, true)
    end)
    bee.addClick(self.ConfirmButton, function()
        Game:playSound("ui_button_confirm")
        bee.setText(self.TextTips, "")
        if self._params.kind == 1 then
            self:onBtCreate()
        else
            self:onBtBind()
        end
    end)
end

function P:onShow()
    bee.setText(self.TextTips, "")
    self.TextPWD:SetActive(false)
    self.TextTimeout:SetActive(false)
    self.UnlinkButton:SetActive(false)

    if self._params.kind == 1 then
        self.InputFieldUID:SetActive(false)
        self.InputFieldPWD:SetActive(false)

        bee.setText(self.TextUID, "UID" .. PlayerModel:getUid())

        Net:post("/player/getAssocPwd", {t = 1}, function(data)
            if bee.isNull(self.node) then
                return
            end
            if 0 == data.code and data.assoc_pwd and "" ~= data.assoc_pwd then
                if data.assoc_pwd_expired and data.assoc_pwd_expired > bee.getServerTime() then
                    self:showBindsInfo(data.assoc_pwd, data.assoc_pwd_expired - bee.getServerTime())
                    self.CloseButton:SetActive(false)
                end
            end
        end)
    else
        self.TextUID:SetActive(false)
        self.InputFieldPWD2:SetActive(false)
        bee.setText(self.TextTitle, _T("LAB_LOGIN_BIND_13"))
    end
end

function P:showBindsInfo(pwd, dt)
    self.InputFieldPWD2:SetActive(false)
    self.TextPWD:SetActive(true)
    bee.setText(self.TextPWD, pwd)
    self.ConfirmButton:SetActive(false)
    self.UnlinkButton:SetActive(true)
    self.TextTimeout:SetActive(true)

    dt = dt or tpl_constdata.AssocTime
    bee.setText(self.TextTimeout, _F("LAB_LOGIN_BIND_08", TimeHelp:getTimeStr(dt)))

    if self._timeTag then
        scheduler:removeTag(self._timeTag)
    end
    self._timeTag = self:schedule(1, function()
        dt = dt - 1
        if dt < 0 then
            dt = 0
        end
        bee.setText(self.TextTimeout, _F("LAB_LOGIN_BIND_08", TimeHelp:getTimeStr(dt)))
        if dt <= 0 then
            bee.logEvent("login-account-transfer code-generate-cancel", 1)
            self:hideUI()
        end
    end)
end

function P:onBtCreate()
    local pwd = bee.getText(self.InputFieldPWD2, "InputField")
    if not GF.isValidPassword(pwd, self.TextTips) then
        return
    end
    Net:post("/player/genAssocPwd", {assoc_pwd = pwd, mask = "genAssocPwd"}, function(data)
        bee.logEvent("login-account-transfer code-generate-confirm")
        if 0 == data.code then
            self:showBindsInfo(pwd, data.assoc_pwd_expired - bee.getServerTime())
            self.CloseButton:SetActive(false)
        else
            local e = tpl_errorCode[data.code]
            if e then
                bee.setText(self.TextTips, _T(e.id))
            end
        end
    end, nil, true)
end

function P:onBtBind()
    local uid = bee.getText(self.InputFieldUID, "InputField")
    uid = string.replace(uid, "UID", "")
    uid = string.replace(uid, "uid", "")
    if "" == uid or tonumber(uid) == nil then
        bee.setText(self.TextTips, _T("LAB_LOGIN_BIND_23"))
        return
    end
    local pwd = bee.getText(self.InputFieldPWD, "InputField")
    if not GF.isValidPassword(pwd, self.TextTips) then
        return
    end
    Net:post("/player/assocUser", {assoc_uid = tonumber(uid), assoc_pwd = pwd}, function(data)
        bee.logEvent("login-account-transfer code-blind-confirm", data and data.assoc_err_num or 0)
        if 0 == data.code then
            UiManager:showTip({
                button = 1,
                noClose = true,
                text = _T("LAB_LOGIN_BIND_22"),
                onSure = function()
			        PlayerModel:setIsLogin(false)
                    Net:closeSocket()
                    bee.enterScene("StartScene")
                end
            })
            self:hideUI()
        else
            local e = tpl_errorCode[data.code]
            if e then
                bee.setText(self.TextTips, _T(e.id))
            end
            if data.code == tpl_HttpCode.HTTP_ASSOC_USER_NOT_EXIST.code then
                return
            end
            local num = tpl_constdata.AssocWrongCount - (data.assoc_err_num or 0)
            if num < 0 then
                num = 0
            end
            UiManager:showTip({
                text = _F("LAB_LOGIN_BIND_19", num),
                -- onCancel = function()
                --     self:hideUI()
                -- end
            })
        end
    end, nil, true)
end

