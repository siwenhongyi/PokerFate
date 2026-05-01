local P = class("CharacterMainBondsUp", UiBase)

function P:onAwake()
	self._openAnim, self._closeAnim = "UI_1_" .. self.__cname .. "_into", "UI_1_" .. self.__cname .. "_back"
    P.super.onAwake(self)
    self:initUI()
end

function P:initUI()
    local AnimRoot = self:find("AnimRoot") or self.node
    local Center = self:find("Center", AnimRoot)
    self.RightTop = self:find("RightTop", AnimRoot)
    self.Bottom = self:find("Bottom", AnimRoot)
    self.ImageMask = self:find("ImageMask", AnimRoot)
    self.LeftTop = self:find("LeftTop", AnimRoot)
    self.CloseMask = self:find("CloseMask", AnimRoot)

    self.CharacterImage = self:find("CharacterImage", Center)
    self.Tips = self:find("Tips", AnimRoot)
    self.TextTip = self:find("TextTip", self.Tips)
    local BondsUp = self:find("BondsUp", self.Bottom)

    self.HeartLvs = {
        self:find("HeartLv1", BondsUp),
        self:find("HeartLv2", BondsUp),
        self:find("HeartLv3", BondsUp),
        self:find("HeartLv4", BondsUp),
        self:find("HeartLv5", BondsUp),
    }

    bee.addClick(self:find("BackButton", self.LeftTop), function()
        self:hideUI()
    end)
    bee.addClick(self:find("CameraButton", self.RightTop), function()
        CS.Utils.CaptureScreen("ScreenCapture/screenshot-" .. os.date("%Y%m%d%H%M%S") .. ".jpg", 3, function()
            UiManager:showToast(_T("LAB_CHAR_072"))
        end)
    end)
    bee.addClick(self:find("ViewButton", self.RightTop), function()
        self.Tips:SetActive(false)
        self.Bottom:SetActive(false)
        self.RightTop:SetActive(false)
        self.LeftTop:SetActive(false)
        self.ImageMask:SetActive(true)
        -- self.parent.BackButton:SetActive(false)
    end)
    bee.addClick2(self.ImageMask, function()
        self.Tips:SetActive(false)
        self.Bottom:SetActive(true)
        self.RightTop:SetActive(true)
        self.LeftTop:SetActive(true)
        self.ImageMask:SetActive(false)
        -- self.parent.BackButton:SetActive(true)
    end)
    bee.addClick2(self.CloseMask, function()
        if scheduler.timeSpend - self._showDt < 1.2 then
            return
        end
        if self.Tips.activeSelf then
            self.Tips:SetActive(false)
            return
        end
        self:hideUI()
    end)
    self.Tips:SetActive(true)
    self.Bottom:SetActive(true)
    self.RightTop:SetActive(true)
    self.LeftTop:SetActive(true)
    self.ImageMask:SetActive(false)
end

function P:onShow()
    self._showDt = scheduler.timeSpend
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
    self:initInfos()
    
    local chats = CharacterModel:getChats(CHAT_VOICE_TYPE.Bond, self._role.role_id)
    if chats then
        local cfg = chats[self._role:getBondLevel() - 1] or chats[1]
        local dt = Game:playRoleOutVoice(self._role.role_id, cfg.key, true)
        bee.setText(self.TextTip, _T(cfg.text))
        self._tipText = cfg.text
        if not dt or dt <= 0 then dt = 3 end
        self:once(dt, function()
            if self._tipText == cfg.text then
                self.Tips:SetActive(false)
            end
        end)
    end

    bee.setAlpha(self.Tips, 0)
    self:once(1, function()
        bee.tween(self.Tips)
        : to(0.5, {alpha = 1})
        : link()
    end)
end

function P:preHide()
    P.super.preHide(self)
    
    UiManager:showUI("CharacterItemsUnlocked", {items = CharacterModel:getRoleBondsRewards(self._role.role_id, self._role:getBondLevel()), role = self._role})
end

function P:initInfos()
    local level = self._role:getBondLevel()
    for i = 1, level do
        local heart = self.HeartLvs[i]
        if heart then
            if i == level then
                self:once(0.3, function()
                    AnimationMgr:playUIEffect("Prefab/Eff_poker_bonds_levelup", heart.transform, bee.v3zero, 2, true)
                    self:once(0.2, function()
                        self:find("on", heart):SetActive(true)
                        self:find("off", heart):SetActive(false)
                    end)
                end)
            else
                self:find("on", heart):SetActive(true)
                self:find("off", heart):SetActive(false)
            end
        end
    end
end

return P