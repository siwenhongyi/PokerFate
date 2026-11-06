local P = class("MatsuriPlayer", UiDialog)

function P:onAwake()
    self._isMute = true
    self.Panel = self:find("AnimRoot/Center/Panel")

    self.title_limited = self:find("title_limited", self.Panel)
    self.btn_choose = self:find("ChooseButton", self.Panel)
    self.btn_gray_choose = self:find("ChooseGrayButton", self.Panel)
    self.btn_to_get = self:find("ToGetButton", self.Panel)
    self.btn_use = self:find("UsingButton", self.Panel)
    self.btn_scheme = self:find("DecorationSchemeItem", self.Panel)

    self.Player = self:find("Player", self.Panel)
    self.PiyoList = self:find("PiyoList", self.Player)
    self.PiyoView = self:find("PiyoView", self.Player)
    self.Item = self:find("Item1", self.Player)
    self.Item:SetActive(false)

    self.index = -1

    bee.addClick(self:find("CloseButton", self.Panel), function()
        Game:playSound("ui_button_confirm")
        self:hideUI()
    end)

    bee.addClick(self.btn_choose, function()
        Game:playSound("ui_button_confirm")
        if bee.checkCd("Theme_btn_choose_player", 2) then
            bee.logEvent("activity-theme-select-use", ActivityId.Matsuri, self._params.game_type, self._selectedId)
            ThemeModel:setCurSkin(self._selectedId)
            -- bee.logEvent("onsen-onsen-character_select_use", GameModel.selectRoomGameType, self._selectedId)
        end
    end)

    bee.addClick(self.btn_gray_choose, function()
        Game:playSound("ui_button_confirm")
        local skinCfg = tpl_character_skin[self._selectedId]
        local roleData = CharacterModel:getRoleData(skinCfg.role)
        local isCanJump = ItemModel:isCanJump(roleData.info.accesses, roleData.role_id)
        UiManager:showTip({
            text = isCanJump and _T("LAB_WARDROBE_1") or _T("LAB_WARDROBE_2"),
            sureStr = isCanJump and _T("LAB_PATH_BUTTON_TEXT_1") or _T("LAB_CONFIRM"),
            button = 1,
            onSure = function()
                if isCanJump then
                    ItemModel:jumpView(roleData.info.accesses[1], roleData.role_id, function()
                        if not bee.isNull(self.node) then
                            self:refreshEvent()
                        end
                    end)
                end
            end
        })
    end)

    bee.addClick(self.btn_to_get, function()
        Game:playSound("ui_button_confirm")
        --local d = tpl_character[tpl_character_skin[self._selectedId].role]
        local skinCfg = tpl_character_skin[self._selectedId]
        bee.logEvent("activity-theme-select-link", ActivityId.Matsuri, self._params.game_type, skinCfg.id)
        local jumpId = skinCfg.role
        if skinCfg.accesses[1] == 102001 then
            jumpId = self._selectedId
        end
        ItemModel:jumpView(skinCfg.accesses[1], jumpId, function ()
            if not bee.isNull(self.node) then
                self:refreshEvent()
            end
        end)
        -- bee.logEvent("onsen-character_select_link", GameModel.selectRoomGameType, self._selectedId)
    end)

    bee.addClick(self.btn_scheme, function ()
        Game:playSound("ui_button_confirm")
        ItemModel:jumpView(13002, nil, function ()
            if not bee.isNull(self.node) then
                self:refreshEvent()
            end
        end)
        bee.logEvent("style-preset-activity-role-choose", ThemeModel:getConfId())
    end)
end

function P:onShow()
    local data = tpl_theme_activity[ThemeModel:getConfId()]
    -- bee.logEvent("onsen-character_select", GameModel.selectRoomGameType)

    self._selectedItem = nil
    self._selectedRoleId = nil
    self._selectedId = nil
    self._Items = {}
    self._datas = {}

    local skinAddList = ThemeModel:getSkinAddEffectList()
    if skinAddList == nil then
        self.title_limited:SetActive(false)
        self.btn_choose:SetActive(false)
        self.btn_gray_choose:SetActive(false)
        self.btn_to_get:SetActive(false)
        self.btn_use:SetActive(false)
        self.btn_scheme:SetActive(false)
        return
    end

    local count = #skinAddList / 2
    local View = self.PiyoView
    if count > 4 then
        View = self:find("Viewport/Content", self.PiyoList)
    else
    end
    self:removeAllChildren(View)
    -- local schemeInfo = DecorationModel:getInGameCurScheme()
    -- local curSkin = 0
    -- if schemeInfo then
    --     curSkin = schemeInfo.skin_id
    -- end
    local skinData = ThemeModel:getCurSkinAddData()
    for i = 1, #skinAddList - 1, 2 do
        local skinId = skinAddList[i]
        local item = CU.GameObject.Instantiate(self.Item, View.transform, false)
        item:SetActive(true)
        self._Items[#self._Items + 1] = item
        local roleId = tpl_character_skin[skinId].role
        self._datas[#self._datas + 1] = {role_id = roleId, skin_id = skinId, add = skinAddList[i + 1]}
        self:refreshItem(self._datas[#self._datas], item, i)
        if skinData and skinId == skinData[1] then
            self._selectedItem = item
        end
    end
    
    if not self._selectedItem then
        local skinId = skinAddList[1]
        local roleId = tpl_character_skin[skinId].role
        self:refreshSelected(self._Items[1], roleId, skinId)
    else
        self:refreshSelected(self._selectedItem, self._selectedRoleId, self._selectedId, true)
    end

    bee.once(0.1, function ()
        self:jumpToRole()
    end)
end

function P:refreshItem(data, item, index)
    local skinCfg = tpl_character_skin[data.skin_id]
    bee.setTextCut(self:find("Name", item), CharacterModel:getRoleName(data.role_id), 155)
    bee.setText(self:find("SkinName", item), _T(skinCfg.name))
    local UsingFrame = self:find("matsuri_tc_frame_chose_02", item)
    local NormalFrame = self:find("matsuri_tc_frame_chose_01", item)
    local SelectFrame = self:find("matsuri_tc_frame_chose_00", item)
    local ImageIcon = self:find("GalaSeason_player_img_character_01", item)
    SelectFrame:SetActive(false)

    local inUseText = self:find("InUse", item)
    local inRandomText = self:find("InRandom", item)
    local isRandom = DecorationModel:isInGameSchemeRandom()
    if not isRandom then
        inRandomText:SetActive(false)
        local isUsing = DecorationModel:checkSkinInScheme(SchemeTag.Ingame, true, data.skin_id)
        inUseText:SetActive(isUsing)
        if isUsing then
            UsingFrame:SetActive(true)
            NormalFrame:SetActive(false)
            if index ~= nil then
                self.index = (index - 1) / 2
            end
            SelectFrame:SetActive(true)
            self._selectedItem = item
            self._selectedRoleId = data.role_id
            self._selectedId = data.skin_id
        else
            UsingFrame:SetActive(false)
            NormalFrame:SetActive(true)
        end
    else
        inUseText:SetActive(false)
        local inRandom = DecorationModel:checkSkinInScheme(SchemeTag.Ingame, false, data.skin_id)
        inRandomText:SetActive(inRandom)
        if inRandom then
            if index ~= nil and self.index == -1 then
                self.index = (index - 1) / 2
                SelectFrame:SetActive(true)
                self._selectedItem = item
                self._selectedRoleId = data.role_id
                self._selectedId = data.skin_id
            end
            UsingFrame:SetActive(true)
            NormalFrame:SetActive(false)
        else
            UsingFrame:SetActive(false)
            NormalFrame:SetActive(true)
        end
    end

    -- local roleId = CharacterModel:getUsingRoleId()
    -- local skinData = CharacterModel:getRoleSkinData(roleId)
    -- if data.skin_id == skinData.id then
    --     self:find("InUse", item):SetActive(true)
    --     UsingFrame:SetActive(true)
    --     NormalFrame:SetActive(false)
    --     if index ~= nil then
    --         self.index = (index - 1) / 2
    --     end
    -- else
    --     self:find("InUse", item):SetActive(false)
    --     UsingFrame:SetActive(false)
    --     NormalFrame:SetActive(true)
    -- end


    bee.setIcon(ImageIcon, skinCfg.ui_avatar_1)

    local roleData = CharacterModel:getRoleData(data.role_id)
    local isRoleLock = roleData.locked
    local isSkinLock = not roleData:isOwnedSkin(data.skin_id)
    bee.setGrey(ImageIcon, isSkinLock)
    bee.setGrey(NormalFrame, isSkinLock)
    self:find("icon_lock_0", item):SetActive(isSkinLock)

    bee.setText(self:find("Value", item), " +" .. data.add / 10 .. "%")

    local propIcon = self:find("icon_activity_s7_01", item)
	bee.setIcon(propIcon, ThemeModel:getThemeIcon())

    bee.addClick(item, function()
        self:refreshSelected(item, data.role_id, data.skin_id)
    end)
end

function P:refreshSelected(item, roleId, skinId, force)
    if item == self._selectedItem and not force then
        self:find("matsuri_tc_frame_chose_00", item):SetActive(true)
        return
    end
    if self._selectedItem then
        self:find("matsuri_tc_frame_chose_00", self._selectedItem):SetActive(false)
    end
    self._selectedItem = item
    self._selectedRoleId = roleId
    self._selectedId = skinId
    self:find("matsuri_tc_frame_chose_00", item):SetActive(true)

    local isRandom = DecorationModel:isInGameSchemeRandom()
    if not isRandom then
        local isUsing = DecorationModel:checkSkinInScheme(SchemeTag.Ingame, true, skinId)
        if isUsing then
            self.title_limited:SetActive(false)
            self.btn_choose:SetActive(false)
            self.btn_gray_choose:SetActive(false)
            self.btn_to_get:SetActive(false)
            self.btn_use:SetActive(true)
            self.btn_scheme:SetActive(false)
        else
            local roleData = CharacterModel:getRoleData(roleId)
            local ownSkin = roleData:isOwnedSkin(skinId)
            if ownSkin then
                self.title_limited:SetActive(false)
                self.btn_to_get:SetActive(false)
                self.btn_use:SetActive(false)
                self.btn_scheme:SetActive(false)
                if not roleData.locked then
                    self.btn_choose:SetActive(true)
                    self.btn_gray_choose:SetActive(false)
                else
                    self.btn_choose:SetActive(false)
                    self.btn_gray_choose:SetActive(true)
                end
            elseif ItemModel:isCanJump(tpl_character_skin[skinId].accesses, skinId) then
                self:setJumpEventBtns()
            else
                self:setLimitEventBtns()
            end
        end
    else
        local inRandom = DecorationModel:checkSkinInScheme(SchemeTag.Ingame, false, skinId)
        if inRandom then
            self.title_limited:SetActive(false)
            self.btn_choose:SetActive(false)
            self.btn_gray_choose:SetActive(false)
            self.btn_to_get:SetActive(false)
            self.btn_use:SetActive(false)
            self.btn_scheme:SetActive(true)
        else
            local roleData = CharacterModel:getRoleData(roleId)
            local ownSkin = roleData:isOwnedSkin(skinId)
            if ownSkin then
                self.title_limited:SetActive(false)
                self.btn_to_get:SetActive(false)
                self.btn_use:SetActive(false)
                if not roleData.locked then
                    self.btn_choose:SetActive(false)
                    self.btn_gray_choose:SetActive(false)
                    self.btn_scheme:SetActive(true)
                else
                    self.btn_choose:SetActive(false)
                    self.btn_gray_choose:SetActive(true)
                    self.btn_scheme:SetActive(false)
                end
            elseif ItemModel:isCanJump(tpl_character_skin[skinId].accesses, skinId) then
                self:setJumpEventBtns()
            else
                self:setLimitEventBtns()
            end
        end
    end
end
function P:setJumpEventBtns()
    self.title_limited:SetActive(false)
    self.btn_choose:SetActive(false)
    self.btn_gray_choose:SetActive(false)
    self.btn_to_get:SetActive(true)
    self.btn_use:SetActive(false)
    self.btn_scheme:SetActive(false)
end
function P:setLimitEventBtns()
    self.title_limited:SetActive(true)
    self.btn_choose:SetActive(false)
    self.btn_gray_choose:SetActive(false)
    self.btn_to_get:SetActive(false)
    self.btn_use:SetActive(false)
    self.btn_scheme:SetActive(false)
end

function P:jumpToRole()
    if self.index <= 0 then
        return
    end

    local showWidth = self.PiyoList:GetComponent("RectTransform").sizeDelta.x
    local piyoRect = bee.find("Viewport/Content", self.PiyoList):GetComponent("RectTransform")
    local totalWidth = piyoRect.sizeDelta.x
    local limitWidth = totalWidth - showWidth * 0.5
    local cacheWidth = 190 * self.index
    local targetPos = math.min(limitWidth, cacheWidth)
    piyoRect.anchoredPosition = bee.v2(targetPos * -1, 0)
end

function P:evt_updateScheme()
    self:hideUI()
end

function P:evt_RoleUnlockRSP()
    self:refreshEvent()
end

function P:evt_SkinUnlockRSP()
    self:refreshEvent()
end

function P:evt_updateInGameScheme()
    self:refreshEvent()
end

function P:refreshEvent()
    for k, v in ipairs(self._Items) do
        self:refreshItem(self._datas[k], v)
    end
    self:refreshSelected(self._selectedItem, self._selectedRoleId, self._selectedId, true)
end

return P