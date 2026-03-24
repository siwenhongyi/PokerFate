local P = class("CharacterOathFulfilled", UiBase)

function P:onAwake()
	self._openAnim, self._closeAnim = "UI_1_" .. self.__cname .. "_into", "UI_1_" .. self.__cname .. "_back"

    local AnimRoot = self:find("AnimRoot") or self.node
    local Center = self:find("Center", AnimRoot)
    self.RightTop = self:find("RightTop", AnimRoot)
    self.Bottom = self:find("Bottom", AnimRoot)
    self.ImageMask = self:find("ImageMask", AnimRoot)
    self.LeftTop = self:find("LeftTop", AnimRoot)

    self.CharacterImage = self:find("CharacterImage", Center)
    self.Tips = self:find("Tips", Center)
    self.TextTip = self:find("TextTip", self.Tips)

    bee.addClick(self:find("BackButton", self.LeftTop), function()
        self:hideUI()
    end)
    bee.addClick(self:find("CameraButton", self.RightTop), function()
        Game:playSound("ui_share_screenshot")
        CS.Utils.CaptureScreen("ScreenCapture/screenshot-" .. os.date("%Y%m%d%H%M%S") .. ".jpg", 3, function()
            UiManager:showToast(_T("LAB_CHAR_072"), nil, nil, true)
        end)
    end)
    bee.addClick(self:find("ViewButton", self.RightTop), function()
        Game:playSound("ui_button_confirm")
        self.Tips:SetActive(false)
        self.Bottom:SetActive(false)
        self.RightTop:SetActive(false)
        self.LeftTop:SetActive(false)
        self.ImageMask:SetActive(true)
    end)
    bee.addClick(self.ImageMask, function()
        self.Tips:SetActive(false)
        self.Bottom:SetActive(true)
        self.RightTop:SetActive(true)
        self.LeftTop:SetActive(true)
        self.ImageMask:SetActive(false)
    end)
    self.Tips:SetActive(true)
    self.Bottom:SetActive(true)
    self.RightTop:SetActive(true)
    self.LeftTop:SetActive(true)
    self.ImageMask:SetActive(false)
end

function P:onShow()
    self.Tips:SetActive(true)
    self.Bottom:SetActive(true)
    self.RightTop:SetActive(true)
    self.LeftTop:SetActive(true)
    self.ImageMask:SetActive(false)

    if self._params then
        self._role = self._params.data

        -- bee.invoke(self.CharacterImage, "setRole", self._role, true)
        local roleImage = CharacterModel:getRoleImage()
        roleImage.transform:SetParent(self.CharacterImage.transform, false)
        bee.invoke(roleImage, "setRole", self._role, true)
    end

    local dt = Game:playRoleOutVoice(self._role.role_id, tpl_chat_voice.awaken, true)
    bee.setText(self.TextTip, _T(self._role.info.awaken_tip))
    self._tipText = self._role.info.awaken_tip
    if not dt or dt <= 0 then dt = 3 end
    self:once(dt, function()
        if self._tipText == self._role.info.awaken_tip then
            self.Tips:SetActive(false)
        end
    end)
end

function P:onHide()
    bee.emit(EventDef.evt_role_awakened_back_to_bonds, self.__cname)
    P.super.onHide(self)
end

