local P = class("CharacterBase", require("app.views.Character.CharacterBaseNameCard"))

function P:onAwake()
    P.super.onAwake(self)

    self.AnimRoot = self:find("AnimRoot")
    self.LeftTop = self:find("LeftTop", self.AnimRoot)
    self.LeftBottom = self:find("LeftBottom", self.AnimRoot)
    self.Left = self:find("Left", self.AnimRoot)
    self.Right = self:find("Right", self.AnimRoot)
    self.RightTop = self:find("RightTop", self.AnimRoot)
    self.Center = self:find("Center", self.AnimRoot)

    self.PageNextButton = self:find("PageNextButton", self.Center) or self:find("PageNextButton", self.AnimRoot)
    self.PageLastButton = self:find("PageLastButton", self.Center)
    if not self.PageNextButton then
        self.PageNextButton = self:find("PageNextButton", self.Right)
    end
    if not self.PageLastButton then
        self.PageLastButton = self:find("PageLastButton", self.Left)
    end
    self.CharacterImage = self:find("CharacterImage", self.Center)
    self.GarmentsNotOwned = self:find("GarmentsNotOwned", self.Center)
    self.FilesTips = self:find("FilesTips", self.Center) or self:find("FilesTips", self.AnimRoot)
    if self.FilesTips then
        self.FilesTips:SetActive(false)
    end

    bee.addClick(self:find("BackButton", self.LeftTop), function()
        self:onBtClose()
        if self.__cname ~= "CharacterMain" then
            bee.emit(EventDef.evt_role_back_to_main, self.__cname)
        end
    end)

    bee.addClick(self:find("LobbyButton", self.LeftTop), function()
        self._openAnim, self._closeAnim = nil, "UI_1_" .. self.__cname .. "_backall"
        self:hideUI()
        UiManager:hideAllUI({"LobbyLayer"})
        -- UiManager:hideUI("CharacterMain")
        if self.__cname == "CharacterMainGarments" then
            bee.logEvent("character-wardrobe-home")
        elseif self.__cname == "CharacterMainProfile" then
            bee.logEvent("character-analysis-home")
        elseif self.__cname == "CharacterMainBonds" then
            bee.logEvent("character-bond-home")
        end
    end)

    bee.addClick(self.PageNextButton, function()
        Game:playSound("ui_button_confirm")
        self:moveSelect(1)
    end)

    bee.addClick(self.PageLastButton, function()
        Game:playSound("ui_button_confirm")
        self:moveSelect(-1)
    end)

    bee.addClick(self:find("ClaimButton", self.GarmentsNotOwned), function()
        Game:playSound("ui_button_confirm")
        ItemModel:jumpView(self._role.info.accesses[1], self._role.role_id, function()
            if not bee.isNull(self.node) then
                self:refreshRole()
            end
        end)
    end)

    self._datas = CharacterModel:getAllCharacters()
end

function P:onShow()
    P.super.onShow(self)
    if self._RoleCanvas and (not self._params or self._params.roleCanvas ~= self._RoleCanvas) then
        self._RoleCanvas = nil
        if self._CharacterImage then
            CU.GameObject.Destroy(self._CharacterImage)
            self._CharacterImage = nil
        end
    else
        self._RoleCanvas = self._params and self._params.roleCanvas
    end
end

function P:onHide()
    P.super.onHide(self)
    Game:stopRoleSound()
    if nil ~= self._RoleCanvas and not (self._params and self._params.roleCanvas == self._RoleCanvas) then
        self._RoleCanvas:hideUI()
        self._RoleCanvas = nil
    end
end

function P:onBtClose()
    self:hideUI()
end

function P:refreshUI()
    self:refreshRole()
    self:refreshBondLevel()
end

function P:refreshRole()
    if nil == self._RoleCanvas then
        self._RoleCanvas = CharacterModel:getRoleCanvas()
    end
    if bee.isNull(self._CharacterImage) then
        self._CharacterImage = self._RoleCanvas:getRoleImage()
        if self._CharacterImage then
            self._CharacterImage.transform:SetParent(self.CharacterImage.transform, false)
        end
    end
    bee.invoke(self._CharacterImage, "setRole", self._role, true)

    -- local roleImage = CharacterModel:getRoleImage()
    -- roleImage.transform:SetParent(self.CharacterImage.transform, false)
    -- bee.invoke(roleImage, "setRole", self._role, true)
end

function P:setSelect(index)
    self._role = self._datas[index]
    self:refreshName()
    self:refreshLeftRight()
    self:refreshUI()
    self:refreshBondLevel()
    CharacterModel:refreshReddot(self._role.role_id)
end

function P:refreshBondLevel()
end

function P:refreshName()
    P.super.refreshName(self)
    self:refreshNoOwned()
end

function P:refreshNoOwned()
    if self._role and self.GarmentsNotOwned  then
        self.GarmentsNotOwned:SetActive(self._role.locked)
        if self._role.locked then
            self:_refreshNoOwned(self._role.info.accesses, self._role.info.id)
        end
    end
end

function P:_refreshNoOwned(accesses, id)
    if not self.GarmentsNotOwned then
        return
    end
    if accesses then
        if ItemModel:isCanJump(accesses, id) then
            self:find("character_owned_limited", self.GarmentsNotOwned):SetActive(false)
            self:find("ClaimButton", self.GarmentsNotOwned):SetActive(true)
        else
            self:find("character_owned_limited", self.GarmentsNotOwned):SetActive(true)
            self:find("ClaimButton", self.GarmentsNotOwned):SetActive(false)
        end
    else
        self:find("character_owned_limited", self.GarmentsNotOwned):SetActive(true)
        self:find("ClaimButton", self.GarmentsNotOwned):SetActive(false)
    end
end

function P:refreshLeftRight()
    local index = self:_getSelectIndex()
    if self.PageLastButton then
        -- self.PageLastButton:SetActive(index ~= 1 and #self._datas > 1)
        -- self.PageNextButton:SetActive(index ~= #self._datas and #self._datas > 1)
    end
end

function P:_getSelectIndex()
    local index = nil
    if self._datas then
        for k, v in ipairs(self._datas) do
            if v == self._role then
                index = k
                break
            end
        end
    end
    return index
end

function P:moveSelect(offset)
    local index = self:_getSelectIndex()
    if index then
        local i = index + offset
        if i < 1 then
            i = #self._datas
        elseif i > #self._datas then
            i = 1
        end
        local d = self._datas[i]
        if d then
            self:setSelect(i)
            -- self:setSelect(d, self.CharacterList:getNode(index + offset))
        end
    end
end

function P:playOpenAnim()
    if self._params and self._params.from == "Character" then
        self:playAnimator("UI_1_" .. self.__cname .. "_switch")
	    --self._openAnim, self._closeAnim = nil, "UI_1_" .. self.__cname .. "_back"
    else
        self:playAnimator("UI_1_" .. self.__cname .. "_into")
	    --self._openAnim, self._closeAnim = nil, "UI_1_" .. self.__cname .. "_backall"
    end
end

function P:evt_RoleGiftRSP(msg)
    self:refreshBondLevel()
end

function P:evt_RoleAwakenRSP(msg)
    self:refreshBondLevel()
end

function P:evt_RoleUnlockRSP(msg)
    if msg.role_info.role_id == self._role.role_id and self.GarmentsNotOwned then
        self.GarmentsNotOwned:SetActive(self._role.locked)
    end
end

return P