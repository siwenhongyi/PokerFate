local P = class("CharacterMainGarments", require("app.views.Character.CharacterBase"))

function P:onAwake()
    P.super.onAwake(self)
	self._closeAnim = ""

    local Garments = self:find("Garments", self.Right)
    -- self.SkinList = self:find("SkinList", Garments)
    self.GarmentsList = self:find("GarmentsList", Garments)
    self.TextName2 = self:find("TextName2", Garments)
    self.TextCV2 = self:find("TextCV2", Garments)

    self.Item1 = self:find("Item1", self.GarmentsList)
    self.Item1:SetActive(false)

    self.character_analysis_bg_kinshi = self:find("character_analysis_bg_kinshi", self.Center)

    self.TextSkin = self:find("TextSkin", self.LeftBottom)

    self.EU = self:find("EU", Garments)
    self.WearButton = self:find("WearButton", Garments)
    self.WearButton2 = self:find("WearButton2", Garments)
    self.EUButton = self:find("EU/EUButton", Garments)
    self.EquipButton = self:find("EU/EquipButton", Garments)
    self.UseButton = self:find("UseButton", Garments)
    self.ClaimButton = self:find("ClaimButton", Garments)

    self.GarmentTag = self:find("GarmentTag", Garments)
    self.GarmentTags = {
        self:find("character_garment_tag_01", self.GarmentTag),
        self:find("character_garment_tag_02", self.GarmentTag),
        self:find("character_garment_tag_03", self.GarmentTag),
        self:find("character_garment_tag_04", self.GarmentTag),
    }

    bee.addClick(self:find("InfoButton", Garments), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonTextTipUD", {text = _T("LAB_CHAR_098"), target = self:find("InfoButton", Garments)})
        bee.logEvent("character-wardrobe-info")
    end)
    self.EditButton = self:find("EditButton", Garments)
    bee.addClick(self.EditButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CharacterChangeName", {data = self._role})
        bee.logEvent("character-wardrobe-edit")
    end)

    bee.addClick(self.WearButton, function()
        Game:playSound("ui_button_confirm")
        self._old_skin_id = self._role:getUsingSkin()
        CharacterModel:changeUsingSkin(self._skins[self._selectIndex].id)
        bee.logEvent("character-wardrobe-wear", self._skins[self._selectIndex].id)
        self._tag = 1
    end)

    bee.addClick(self.WearButton2, function()
        Game:playSound("ui_button_confirm")
        local isCanJump = ItemModel:isCanJump(self._role.info.accesses, self._role.role_id)
        UiManager:showTip({
            text = isCanJump and _T("LAB_WARDROBE_1") or _T("LAB_WARDROBE_2"),
            sureStr = isCanJump and _T("LAB_PATH_BUTTON_TEXT_1") or _T("LAB_CONFIRM"),
            button = 1,
            onSure = function()
                if isCanJump then
                    ItemModel:jumpView(self._role.info.accesses[1], self._role.role_id, function()
                        if not bee.isNull(self.node) then
                            self:refreshNoOwned()
                            self:refreshSelectSkinInfo()
                        end
                    end)
                end
            end
        })
        bee.logEvent("character-wardrobe-wear-not-character", self._skins[self._selectIndex].id)
    end)

    bee.addClick(self.EUButton, function()
        Game:playSound("ui_button_confirm")
        self._old_skin_id = self._role:getUsingSkin()
        CharacterModel:changeUsingSkin(self._skins[self._selectIndex].id)
        bee.logEvent("character-wardrobe-equip-use", self._skins[self._selectIndex].id)
        self._tag = 2
    end)

    bee.addClick(self.EquipButton, function()
        Game:playSound("ui_button_confirm")
        self._old_skin_id = self._role:getUsingSkin()
        Net:sendReq("pb.SwitchRoleSkinREQ", {
            role_id = self._role.role_id,
            new_skin_id = self._skins[self._selectIndex].id,
        })
        bee.logEvent("character-wardrobe-equip", self._skins[self._selectIndex].id)
        self._tag = 3
    end)

    bee.addClick(self.UseButton, function()
        Game:playSound("ui_button_confirm")
        self._old_skin_id = self._role:getUsingSkin()
        CharacterModel:changeUsingSkin(self._role:getUsingSkin())
        bee.logEvent("character-wardrobe-use", self._skins[self._selectIndex].id)
        self._tag = 4
    end)

    bee.addClick(self.ClaimButton, function()
        local skin = self._skins[self._selectIndex]
        local r = CharacterModel:getRole(self._role.role_id)
        if r or skin.kind == SKIN_KIND.PAY then
            if skin.kind == SKIN_KIND.PAY then
                ItemModel:jumpView(skin.accesses[1] or 0, skin.id)
            else
                ItemModel:jumpView(skin.accesses[1] or 0, skin.role)
            end
        else
            if skin.kind == SKIN_KIND.AWAKEN then
                UiManager:showTip({
                    text = _T("LAB_CHAR_118"),
                    button = 1,
                    sureStr = _T("LAB_PATH_BUTTON_TEXT_1"),
                    onSure = function()
                        ItemModel:jumpView(tpl_character[self._role.role_id].accesses[1] or 0, self._role.role_id)
                    end
                })
            else
                ItemModel:jumpView(tpl_character[self._role.role_id].accesses[1] or 0, self._role.role_id)
            end
        end
        Game:playSound("ui_button_confirm")
        -- UiManager:hideUI("CharacterMain")
        -- self:hideUI()
    end, true)
    
    bee.addClick(self:find("BustButton", self.Left), function()
        if not bee.checkCd("character_bust_click", 4) then
            return
        end
        bee.invoke(self._CharacterImage, "playScrap")
        bee.logEvent("character-preview-bust")
        Game:playSound("ui_button_confirm")
    end)
    bee.addClick(self:find("AllInButton", self.Left), function()
        -- UiManager:showUI("CharacterViewVictory", {role = self._role, skin = self._skins[self._selectIndex]})
        UiManager:showUI(GameModel:getAllinUiName(), {role = self._role, skin = self._skins[self._selectIndex]})
        bee.logEvent("character-preview-allin")
        Game:playSound("ui_button_confirm")
    end)
    bee.addClick(self:find("TableButton", self.Left), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("BackpackPreview", {role = self._role, skin = self._skins[self._selectIndex]})
        bee.logEvent("character-preview-table")
    end)
    bee.addClick(self:find("InfoButton", self.Left), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CharacterView", {data = self._role, skin = self._skins[self._selectIndex]})
        bee.logEvent("character-preview-illustrator")
    end)

    self._nodeCache = NodeCache:create()

    self.ListGarments = UiListEx:create(self.GarmentsList)
    self.ListGarments:setWidth(220)
    self.ListGarments:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(self.Item1)
    end)
    self.ListGarments:setRefreshFunc(function(data, item)
        self:refreshSkinItem(data, item)
    end)
    self._SkinNodes = {}
end

function P:onShow()
    P.super.onShow(self)
    self._role = self._params.data or self._datas[1]

    self:refreshLeftRight()

    self:refreshName()
    self:refreshUI()

    self:playOpenAnim()

    self:garmentGuide()
end

function P:playOpenAnim()
    if self._params and self._params.from == "Character" then
	    self._openAnim, self._closeAnim = nil, ""
    else
	    self._openAnim, self._closeAnim = nil, ""
    end
end

function P:refreshUI()
    P.super.refreshUI(self)
    if self.ItemsTras then
        for _, v in ipairs(self.ItemsTras) do
            self._nodeCache:putItem(v.gameObject)
        end
    end

    local initId = self._params.selectId or self._role:getUsingSkin()

    self._skins = {}
    local skin = get_tpl_subKey(tpl_character_skin_list, "role", self._role.role_id)
    for _, v in ipairs(skin) do
        if not v.display_time or v.display_time <= bee.getServerTime() then
            table.insert(self._skins, v)
        elseif bee.isDev or PlayerModel:isEventWhite() then
            table.insert(self._skins, v)
        end
    end
    self._selectIndex = 1
    for k, v in ipairs(self._skins) do
        if v.id == initId then
            self._selectIndex = k
            break
        end
    end
    self.ListGarments:setDatas(self._skins)
    self.ListGarments:moveToYItem(self._selectIndex)
    self:refreshSelectSkinInfo()
end

-- function P:refreshRole()
--     local roleImage = CharacterModel:getRoleImage("Garments")
--     roleImage.transform:SetParent(self.CharacterImage.transform, false)
--     bee.invoke(roleImage, "setRole", self._role, true)
--     self._CharacterImage = roleImage
-- end

function P:refreshName()
    P.super.refreshName(self)
    self.EditButton:SetActive(not self._role.locked)

    if self._role then
        local d = tpl_character[self._role.role_id]
        bee.setText(self.TextName2, self._role:getName())
        bee.setText(self.TextCV2, "CV:" .. _T(self._role.info.cv))

        if self._skins then
            local skin = self._skins[self._selectIndex]
            bee.setText(self.TextSkin, _T(skin.name))
        else
            bee.setText(self.TextSkin, _T(self._role:getSkinData().name))
        end
    end
end

function P:refreshImageSkin(ImageSkin, data)
    bee.setIcon(ImageSkin, data.image_with_bg or data.image, true)
    if data.hanger_offset then
        ImageSkin.transform.localPosition = bee.v3(data.hanger_offset[1], data.hanger_offset[2])
        ImageSkin.transform.localScale = bee.v3(data.hanger_offset[3], data.hanger_offset[3], data.hanger_offset[3])
    end
end

function P:refreshSkinItem(data, item)
    self._SkinNodes[item] = data
    local isOwned = self._role:isOwnedSkin(data.id)
    if data.id == self._role:getUsingSkin() then
        local skin = self._skins[self._selectIndex]
        if data.role == CharacterModel:getUsingRoleId() or skin.id ~= data.id then
            self:find("In use", item):SetActive(true)
        else
            self:find("In use", item):SetActive(false)
        end
    else
        self:find("In use", item):SetActive(false)
    end
    bee.setText(self:find("TextName", item), _T(data.name))
    self:refreshImageSkin(self:find("On/Mask/ImageSkin", item), data)
    self:refreshImageSkin(self:find("Off/Mask/ImageSkin", item), data)
    self:find("RedNew", item):SetActive(CharacterModel:isNewSkin(data.id))
    self:find("character_garment_tab_time", item):SetActive(false)
    if not isOwned and ItemModel:isCanJump(data.accesses, data.id) then
        local dt = ShopModel:getShopSkinLeftTime(data.id)
        if dt > 0 then
            self:find("character_garment_tab_time", item):SetActive(true)
            bee.setText(self:find("character_garment_tab_time/TextTime", item), ShopModel:getShopTimeText(dt))
        end
    end

    local BgSr = nil
    if data.id == self._skins[self._selectIndex].id then
        self:find("On", item):SetActive(true)
        self:find("Off", item):SetActive(false)
        self:find("character_garment_selected", item):SetActive(true)
        self:find("character_garment_selected_on", item):SetActive(true)
        self:find("character_garment_selected_off", item):SetActive(false)
        BgSr = self:find("On/BgSR", item)
    else
        self:find("On", item):SetActive(false)
        self:find("Off", item):SetActive(true)
        self:find("character_garment_selected", item):SetActive(false)
        self:find("character_garment_selected_on", item):SetActive(false)
        self:find("character_garment_selected_off", item):SetActive(true)
        BgSr = self:find("Off/BgSR", item)
    end
    local srName = nil
    if data.rank == SKIN_RANK.SR then
        srName = "Prefab/Character/Eff_poker_Ui_Sr"
    elseif data.rank == SKIN_RANK.SSR then
        srName = "Prefab/Character/Eff_poker_Ui_Ssr"
    else
    end
    self:removeAllChildren(BgSr)
    if srName then
        local eft = bee.createObj(srName)
        if eft then
            eft.transform:SetParent(BgSr.transform, false)
            eft.transform.localPosition = bee.v3zero
        end
    end

    bee.addClick(item, function()
        Game:playSound("ui_button_confirm")
        if data.id ~= self._skins[self._selectIndex].id then
            for k, v in ipairs(self._skins) do
                if v.id == data.id then
                    self._selectIndex = k
                    break
                end
            end
            self.ListGarments:refreshShowingUi()
            self:refreshSelectSkinInfo()
        end
    end, true)
    self:refreshName()
end

function P:refreshSelectSkin()
    if self._curIndex ~= self._selectIndex then
        self._selectIndex = self._curIndex
        self:refreshSelectSkinInfo()
    end
end

function P:refreshSelectSkinInfo()
    local skin = self._skins[self._selectIndex]
    self.WearButton2:SetActive(false)
    self.ClaimButton:SetActive(false)
    if not self._role:isOwnedSkin(skin.id)then
        self.WearButton:SetActive(false)
        self.EU:SetActive(false)
        self.UseButton:SetActive(false)
        local jump = tpl_Jump_path[skin.accesses[1]]
        if skin.kind == SKIN_KIND.NORMAL then
            if ItemModel:isCanJump(skin.accesses, skin.role) then
                self:showGarmentTag(0)
                self.ClaimButton:SetActive(true)
                bee.setText(self:find("TextFrom", self.ClaimButton), _T(jump.name))
            else
                self:showGarmentTag(4)
            end
        elseif skin.kind == SKIN_KIND.AWAKEN then
            local r = CharacterModel:getRole(skin.role)
            local roleData = tpl_character[skin.role]
            if r and ItemModel:isCanJump(skin.accesses, skin.id) then
                self:showGarmentTag(0)
                self.ClaimButton:SetActive(true)
                bee.setText(self:find("TextFrom", self.ClaimButton), _T(jump.name))
            elseif not r and roleData and ItemModel:isCanJump(roleData.accesses, roleData.id) then
                self:showGarmentTag(0)
                self.ClaimButton:SetActive(true)
                bee.setText(self:find("TextFrom", self.ClaimButton), _T(jump.name))
            else
                self:showGarmentTag(4)
            end
        else
            if ItemModel:isCanJump(skin.accesses, skin.id) then
                self:showGarmentTag()
                self.ClaimButton:SetActive(true)
                bee.setText(self:find("TextFrom", self.ClaimButton), _T(jump.name))
            else
                self:showGarmentTag(4)
            end
        end 
    elseif skin.id == self._role:getUsingSkin() then
        self.WearButton:SetActive(false)
        self.EU:SetActive(false)
        self.UseButton:SetActive(false)
        if skin.role == CharacterModel:getUsingRoleId() then
            self:showGarmentTag(1)
        else
            self:showGarmentTag()
            self.UseButton:SetActive(true)
        end
    else
        if self._role.locked then
            self.WearButton2:SetActive(true)
            self.WearButton:SetActive(false)
            self.EU:SetActive(false)
            self.UseButton:SetActive(false)
            self:showGarmentTag()
        else
            self.WearButton:SetActive(false)
            self.EU:SetActive(false)
            self.UseButton:SetActive(false)
            self:showGarmentTag()

            if skin.role == CharacterModel:getUsingRoleId() then
                self.WearButton:SetActive(true)
            else
                self.EU:SetActive(true)
            end
        end
    end
    if self.GarmentsNotOwned then
        self.GarmentsNotOwned:SetActive(not self._role:isOwnedSkin(skin.id))
    end
    bee.setIcon(self.character_analysis_bg_kinshi, "Character[character_analysis_bg_camp_" .. self._role.info.campInt .. "]", true)
    
    if self._role.locked then
        self:refreshNoOwned()
    else
        if not self._role:isOwnedSkin(skin.id) then
            self:_refreshNoOwned(skin.accesses, skin.id)
        end
    end
    
    -- local roleImage = CharacterModel:getRoleImage("Garments")
    -- roleImage.transform:SetParent(self.CharacterImage.transform, false)
    -- bee.invoke(roleImage, "setSkin", skin, true)
    if not bee.isNull(self._CharacterImage) then
        bee.invoke(self._CharacterImage, "setSkin", skin, true)
    end

    CharacterModel:removeSkinRed(skin.id)
    for k, v in pairs(self._SkinNodes) do
        if v.id == skin.id then
            self:find("RedNew", k):SetActive(CharacterModel:isNewSkin(skin.id))
            break
        end
    end
end

function P:showGarmentTag(tag)
    if not tag then
        self.GarmentTag:SetActive(false)
    else
        self.GarmentTag:SetActive(true)
        for k, v in ipairs(self.GarmentTags) do
            v:SetActive(k == tag)
        end
    end
end

function P:refreshItems(offsetX)
    if offsetX then
        for k, v in ipairs(self.Positions) do
            v.x = (k - 1) * self._space + offsetX
        end
    end
    local midTrans, midIndex, minDis = nil, 1, 999999
    for k, v in ipairs(self.ItemsTras) do
        v.transform.localPosition = self.Positions[k]
        if math.abs(self.Positions[k].x) < minDis then
            midTrans, midIndex, minDis = v, k, math.abs(self.Positions[k].x)
        end
    end
    if midTrans then
        for k, v in ipairs(self.ItemsTras) do
            local s = 1 - self._scaleRate * math.abs(self.Positions[k].x)
            v.localScale = bee.v3(s, s, s)
        end
        midTrans:SetAsLastSibling()
        for i = 1, midIndex - 1 do
            self.ItemsTras[i]:SetSiblingIndex(i - 1)
        end
        for i = #self.ItemsTras, midIndex + 1, -1 do
            self.ItemsTras[i]:SetSiblingIndex(#self.ItemsTras - 2)
        end
        self._curTrans = midTrans
        self._curIndex = midIndex

        self:refreshSelectSkin()
    end
end

function P:evt_updateScheme(msg)
    self.ListGarments:refreshShowingUi()
    self:refreshSelectSkinInfo()
    if self._tag == 2 then
        UiManager:showToast(_T("LAB_CHAR_104"))
    elseif self._tag == 4 then
        UiManager:showToast(_T("LAB_CHAR_103"))
    end
end

function P:evt_SwitchRoleSkinRSP(msg)
    self.ListGarments:refreshShowingUi()
    self:refreshSelectSkinInfo()
    if self._tag == 1 or self._tag == 3 then
        UiManager:showToast(_T("LAB_CHAR_102"))
    end
end

function P:evt_SkinUnlockRSP(msg)
    self.ListGarments:refreshShowingUi()
    self:refreshSelectSkinInfo()
end

--引导
function P:garmentGuide()
    GuideManager:startSystemGuide(5001, 0.65)
end
function P:evt_refresh_character_pos()
    local cfg = tpl_guide[5001]
    local point = bee.find(cfg.show_ui[1], UiManager:getUiRoot())
    for k,v in pairs(self._SkinNodes) do
        if v.id == self._skins[self._selectIndex].id then
            point.transform.position = k.transform.position
        end
    end
end

return P
