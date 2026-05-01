local P = class("CharacterMain", require("app.views.Character.CharacterBase"))

function P:onAwake()
    P.super.onAwake(self)
    self._isBase = true
	self._openAnim, self._closeAnim = "UI_1_" .. self.__cname .. "_into", "UI_1_" .. self.__cname .. "_back"

    self.bg_character_bg_hellhound = self:find("bg_character_bg_hellhound", self.Center)
    self.Characters = self:find("Characters", self.Right)
    self.EmptyCharacters = self:find("Empty", self.Characters)
    local CharacterList = self:find("CharacterList", self.Characters)
    local Item1 = self:find("Item1", CharacterList)
    Item1:SetActive(false)
    
    local TabMain = self:find("TabMain", self.Left)
    self.GarmentToggle = self:find("GarmentToggle", TabMain)
    self.FileToggle = self:find("FileToggle", TabMain)
    self.BondsToggle = self:find("BondsToggle", TabMain)
    self.ImageBond = self:find("ImageBond", self.BondsToggle)
    self.TextBondLevel = self:find("TextBondLevel", self.ImageBond)

    bee.addClick(self.GarmentToggle, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CharacterMainGarments", {data = self._role, roleCanvas = self._RoleCanvas, from = "Character"})
        bee.logEvent("character-wardrobe")
    end)
    bee.addClick(self.FileToggle, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CharacterMainProfile", {data = self._role, roleCanvas = self._RoleCanvas, from = "Character"})
        bee.logEvent("character-analysis")
    end)
    bee.addClick(self.BondsToggle, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CharacterMainBonds", {data = self._role, roleCanvas = self._RoleCanvas, from = "Character"})
        bee.logEvent("character-bond")
    end)

    bee.addClick(self:find("PreviewTableButton", self.Right), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("BackpackPreview", {role = self._role})
        bee.logEvent("character-preview-table")
    end)

    bee.addClick(self:find("PreviewImageButton", self.Right), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CharacterView", {data = self._role})
        bee.logEvent("character-preview-illustrator")
    end)
    
    -- bee.addClick(self:find("CharacteButton", self.Center), function()
    --     if self._sounds and #self._sounds > 0 then
    --         self._sounds = CharacterModel:getCharacterChatList(self._role:getUsingSkin())
    --         Game:playRoleOutVoice(self._role.role_id, self._sounds[math.random(#self._sounds)].sound)
    --         bee.logEvent("character-click-voice")
    --     end
    -- end)

    self.CharacterList = UiListEx:create(CharacterList)
    self.CharacterList:setWidth(300)
    self.CharacterList:setRowCount(3)
    self.CharacterList:setRowPostions({-207, 0, 207})
    self.CharacterList:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(Item1)
    end)
    self.CharacterList:setRefreshFunc(function(data, item)
        self:refreshCharacter(data, item)
    end)
    self.CharacterList:setFlexFunc(function(data, item, pos)
        local p1 = self.CharacterList._content.transform.localPosition
        local x = -(-pos.y - p1.y) * 268 / 1050 + 132
        pos.x = pos.x + x
        return pos
    end)

    local TabChracters = self:find("TabChracters", self.Characters)
    bee.addValueChanged(self:find("CharactersRightToggle", TabChracters), function(isOn)
        if isOn then
            Game:playSound("ui_button_confirm")
            self:showList(3)
        end
    end)
    bee.addValueChanged(self:find("CharactersMidToggle", TabChracters), function(isOn)
        if isOn then
            Game:playSound("ui_button_confirm")
            self:showList(2)
        end
    end)
    bee.addValueChanged(self:find("CharactersLeftToggle", TabChracters), function(isOn)
        if isOn then
            Game:playSound("ui_button_confirm")
            self:showList(1)
        end
    end)

    -- 任务-查看角色界面
    TaskModel:reportTask(TaskType.CheckView, TaskTargetId.Role)

    RedManager:bind(self:find("Reddot", self.GarmentToggle), RedTag.CharacterGarments)
    RedManager:bind(self:find("Reddot", self.FileToggle), RedTag.CharacterProfile)
    RedManager:bind(self:find("Reddot", self.BondsToggle), RedTag.CharacterBonds)
end

function P:onShow()
    P.super.onShow(self)
    self:showList(1)
    if self._params and self._params.skin_id then
        local skinData = tpl_character_skin[self._params.skin_id]
        for k, v in ipairs(self._datas) do
            if v.role_id == skinData.role then
                self:setSelect(k)
                -- bee.setIcon(self.ImageRole, skinData.image)
                break
            end
        end
    end
    self:refreshRole()
end

function P:showList(index)
    self._showIndex = index
    self._selectItem = nil
    self._datas = nil
    if 1 == self._showIndex then
        self._datas = CharacterModel:getAllCharacters()
    elseif 2 == self._showIndex then
        self._datas = CharacterModel:getOwnedCharacters()
    else
        self._datas = CharacterModel:getStarredCharacters()
    end
    if #self._datas > 0 then
        self._role = nil
    end
    for k, v in ipairs(self._datas) do
        v._sortIndex = k
    end
    self.CharacterList:setDatas(self._datas)
    self.EmptyCharacters:SetActive(0 == #self._datas)
    self:refreshSelect()
    
    self:_tryShowGuide()
end

function P:refreshBondLevel()
    if self.ImageBond and self._role then
        local r = CharacterModel:getRole(self._role.role_id)
        if r then
            if r:isAwaken() then
                if self:find("character_icon_goodwill_max", self.BondsToggle) then
                    self:find("character_icon_goodwill_max", self.BondsToggle):SetActive(true)
                    self:find("character_icon_goodwill_normal", self.BondsToggle):SetActive(false)
                end
                self.ImageBond:SetActive(true)
                bee.setText(self.TextBondLevel, Config.AWAKEN_LEVEL)
            else
                if self:find("character_icon_goodwill_max", self.BondsToggle) then
                    self:find("character_icon_goodwill_max", self.BondsToggle):SetActive(false)
                    self:find("character_icon_goodwill_normal", self.BondsToggle):SetActive(true)
                end
                self.ImageBond:SetActive(true)
                bee.setText(self.TextBondLevel, r:getBondLevel())
            end
        else
            if self:find("character_icon_goodwill_max", self.BondsToggle) then
                self:find("character_icon_goodwill_max", self.BondsToggle):SetActive(false)
                self:find("character_icon_goodwill_normal", self.BondsToggle):SetActive(true)
            end
            self.ImageBond:SetActive(false)
        end
    end
end

function P:refreshSelect()
    self:refreshName()
    self:refreshLeftRight()
    
    if self._role then
        local material = ResManager:GetMaterial( "effect/Material/UI/81-90/Mat_UI_88_characterMainProfile_zy0" .. self._role.info.campInt .. ".mat")
        if material then
            self.bg_character_bg_hellhound:GetComponent("Image").material = material
        end

        -- if not self._role.locked then
        --     self._sounds = CharacterModel:getCharacterChatList(self._role:getUsingSkin())
        --     Game:playRoleOutVoice(self._role.role_id, self._role:isAwaken() and tpl_chat_voice.login_awaken or tpl_chat_voice.login)
        -- else
        --     self._sounds = nil
        -- end
    end
end

function P:setSelect(index)
    local data = self._datas[index]
    local item = self.CharacterList:getNode(index)
    self:setSelectData(data, item)
end

function P:setSelectData(data, item)
    if self._selectItem then
        self:find("character_list_grid_selected", self._selectItem):SetActive(false)
    end
    self._role = data
    self._selectItem = item
    if self._selectItem then
        self:find("character_list_grid_selected", self._selectItem):SetActive(true)
    end
    self.GarmentsNotOwned:SetActive(self._role.locked)
    if self._role.locked then
        if self._role.info.accesses then
            self:find("character_owned_limited", self.GarmentsNotOwned):SetActive(false)
            self:find("ClaimButton", self.GarmentsNotOwned):SetActive(true)
        else
            self:find("character_owned_limited", self.GarmentsNotOwned):SetActive(true)
            self:find("ClaimButton", self.GarmentsNotOwned):SetActive(false)
        end
    end
    self:refreshSelect()
    self:refreshRole()
    self:refreshBondLevel()

    if not CharacterModel:removeNewroleRed(self._role.role_id) then
        CharacterModel:refreshReddot(self._role.role_id)
    end
end

function P:_setCharacterItemState(item, data, isLock)
    bee.setGrey(self:find("Mask/ImageIcon", item), isLock)
    bee.setGrey(self:find("character_list_grid", item), isLock)
    local TextName = nil
    if isLock then
        TextName = self:find("BgName/TextNameLock", item)
        bee.setText(self:find("BgName/TextNameColor", item), "")
        bee.setText(self:find("BgName/TextName", item), "")
        -- bee.setTextCut(self:find("BgName/TextNameLock", item), data:getName(), 168)
        self:find("character_list_color", item):SetActive(false)
        self:find("character_list_grid", item):SetActive(true)
    else
        bee.setText(self:find("BgName/TextNameLock", item), "")
        if data:isAwaken() then
            TextName = self:find("BgName/TextNameColor", item)
            self:find("character_list_color", item):SetActive(true)
            self:find("character_list_grid", item):SetActive(false)
            -- bee.setTextCut(self:find("BgName/TextNameColor", item), data:getName(), 168)
            bee.setText(self:find("BgName/TextName", item), "")
        else
            TextName = self:find("BgName/TextName", item)
            self:find("character_list_color", item):SetActive(false)
            self:find("character_list_grid", item):SetActive(true)
            -- bee.setTextCut(self:find("BgName/TextName", item), data:getName(), 168)
            bee.setText(self:find("BgName/TextNameColor", item), "")
        end
    end
    bee.setText(TextName, data:getName())
    local BgName = self:find("BgName", item)
    local s = BgName.transform.sizeDelta
    local len = CS.Utils.GetTextWidth(TextName:GetComponent("Text"), data:getName())
    bee.Tween.killByTarget(TextName)
    if len <= s.x then
        TextName.transform.localPosition = bee.v3zero
    else
        local offset = (len - s.x) / 2 + 10
        TextName.transform.localPosition = bee.v3(offset)
        bee.tween(TextName)
        : to(5, {position = bee.v3(-offset, 0, 0)})
        : delay(3)
        : to(0, {position = bee.v3(offset, 0, 0)})
        : loop(-1)
        : link()
        : setTarget()
    end
end

function P:refreshCharacter(data, item)
    item.name = "Item" .. data._sortIndex
    local d = tpl_character[data.role_id]
    local skin = CharacterModel:getRoleSkinData(data.role_id)
    bee.setIcon(self:find("Mask/ImageIcon", item), skin.ui_avatar_1)
    self:find("tag", item):SetActive(data.role_id == CharacterModel.using_role_id)
    self:find("icon_lock_02", item):SetActive(data.locked)
    self:find("character_list_grid_selected", item):SetActive(self._selectItem == item)

    local RedNew = self:find("RedNew", item)
    RedNew:SetActive(CharacterModel:isNewRole(data.role_id))
    local Reddot = self:find("Reddot", item)
    Reddot:SetActive(CharacterModel:isRoleHaveNewSkin(data.role_id) or CharacterModel:isRoleCanAwakenRed(data.role_id))

    local ToggleStar = self:find("ToggleStar", item)
    ToggleStar:SetActive(not data.locked)
    if not data.locked then
        if not self._stopShowNewAnim and (CharacterModel:isPlayNewRoleAnim(data.role_id)) then
            RedNew:SetActive(false)
            Reddot:SetActive(false)
            self:_setCharacterItemState(item, data, true)
            ToggleStar:SetActive(false)
            self:find("icon_lock_02", item):SetActive(true)
            self:once(1, function()
                AnimationMgr:playUIEffect("Prefab/Character/Eff_poker_Ui_Characters_js", item.transform, nil, nil, true)
                self:once(0.5,function()
                    self:find("icon_lock_02", item):SetActive(false)
                    self:_setCharacterItemState(item, data, false)
                    ToggleStar:SetActive(true)
                    RedNew:SetActive(CharacterModel:isNewRole(data.role_id))
                    Reddot:SetActive(CharacterModel:isRoleHaveNewSkin(data.role_id) or CharacterModel:isRoleCanAwakenRed(data.role_id))
                end)
            end)
        else
            self:_setCharacterItemState(item, data, false)
        end
        self:find("character_list_grid_star_off", ToggleStar):SetActive(not data.is_star)
        self:find("character_list_grid_star_on", ToggleStar):SetActive(data.is_star)
        bee.addClick(ToggleStar, function()
            Game:playSound("ui_button_confirm")
            if not data.is_star and SettingModel:isRoleShowStarDlg() then
                UiManager:showUI("CharacterCollectCharacters", data)
            else
                Net:sendReq("pb.RoleSetStarREQ", {role_id = data.role_id, is_star = not data.is_star})
                bee.logEvent("character-starred", data.role_id, is_star and 0 or 1)
            end
        end, true)
    else
        self:_setCharacterItemState(item, data, true)
    end

    if not self._selectItem then
        self:setSelectData(data, item)
    end

    bee.addClick2(item, function()
        if self._role == data then
            if data.role_id ~= CharacterModel.using_role_id then
                if data.locked then
                    UiManager:showToast(_T("LAB_CHAR_075"))
                else
                    Game:playSound("ui_button_confirm")
                    self._old_role_id = CharacterModel.using_role_id
                    CharacterModel:changeUsingRole(data.role_id)
                    bee.logEvent("character-inuse", data.role_id)
                end
            else
                Game:playSound("ui_button_confirm")
            end
            return
        else
            Game:playSound("ui_button_confirm")
        end
        self:setSelectData(data, item)
    end, true)
end

function P:_refreshItemByRoleId(role_id)
    local r = CharacterModel:getRoleData(role_id)
    if r then
        local n = self.CharacterList:getDataNode(r)
        if n then
            self:refreshCharacter(r, n)
        end
    end
end

function P:_tryShowGuide()
    if 1 == self._showIndex and CharacterModel:isGetroleguide() then
        if GuideManager:startSystemGuide(1001, 2) then
            CharacterModel:removeGetroleguide()
        end
    end
end

function P:evt_RoleRenameRSP(msg)
    P.super.evt_RoleRenameRSP(self, msg)
    local role_id = msg.role_id
    for _, v in ipairs(self._datas) do
        if v.role_id == role_id then
            local n = self.CharacterList:getDataNode(v)
            if n then
                self:refreshCharacter(v, n)
            end
            break
        end
    end
end

function P:evt_RoleSetStarRSP(msg)
    if 3 == self._showIndex then
        self:showList(3)
    else
        self:_refreshItemByRoleId(msg.role_id)
    end
end

function P:evt_updateScheme(schemeInfo)
    if not schemeInfo then
        return
    end
    self.CharacterList:refreshShowingUi()
    self:refreshRole()

    if not UiManager:getUI("CharacterMainGarments") then
        UiManager:showToast(_T("LAB_CHAR_104"))
    end
end

function P:evt_SwitchRoleSkinRSP(msg)
    self.CharacterList:refreshShowingUi()
    self:_refreshItemByRoleId(msg.role_id)
    if UiManager:isTopUI(self.node) then
        self:refreshRole()
    end
end

function P:evt_RoleUnlockRSP(msg)
    P.super.evt_RoleUnlockRSP(self, msg)
    self._stopShowNewAnim = true
    self:_refreshItemByRoleId(msg.role_info.role_id)
    self._stopShowNewAnim = nil
end

function P:evt_role_back_to_main(name)
    if UiManager:isTopUI(self.node) then
        self:once(-1, function()
            if UiManager:isTopUI(self.node) then
                self:refreshRole()
                self:playAnimator(self._openAnim)
                CharacterModel:refreshReddot(self._role.role_id)
            end
        end)
    end
end

function P:evt_uiManagerHideUI(uiName)
    if CharacterModel:isHaveNewRole() then
        if 1 == self._showIndex then
            self._datas = CharacterModel:getAllCharacters()
            for k, v in ipairs(self._datas) do
                v._sortIndex = k
            end
            self.CharacterList:setDatas(self._datas)
            self:setSelect(self._role._sortIndex)
        end
        self:once(0.1, function()
            if UiManager:isTopUI(self.node) then
                self.CharacterList:refreshShowingUi()
                self:_tryShowGuide()
            end
        end)
    end
end

function P:evt_role_role_red(role_id)
    self:_refreshItemByRoleId(role_id)
end

function P:evt_role_newrole_red(role_id)
    self:_refreshItemByRoleId(role_id)
end

function P:evt_role_newskin_red(skin_id)
    local skinData = tpl_character_skin[skin_id]
    if skinData then
        self:_refreshItemByRoleId(skinData.role)
    end
end

function P:evt_role_awaken_red(role_id)
    self:_refreshItemByRoleId(role_id)
end

return P