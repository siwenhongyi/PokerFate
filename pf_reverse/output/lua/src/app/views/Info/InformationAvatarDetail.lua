local P = class("InformationAvatarDetail", UiBase)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Panel = self:find("Center/Panel", self.AnimRoot)

    self.AvatarList = self:find("AvatarList", self.Panel)
    self.AvatarItem1 = self:find("Item1", self.AvatarList)
    self.Current = self:find("Current", self.Panel)
    self.CurrentItem1 = self:find("Item1", self.Current)
    self.BgAdds = {
        self:find("BgAdd1", self.Current),
        self:find("BgAdd2", self.Current),
        self:find("BgAdd3", self.Current),
        self:find("BgAdd4", self.Current),
    }
    self.TipMask = self:find("TipMask", self.Panel)
    self.Tips = self:find("Tips", self.TipMask)
    self.TipItem1 = self:find("Avatar", self.Tips)

    self.AvatarItem1:SetActive(false)
    self.CurrentItem1:SetActive(false)
    self.TipItem1:SetActive(false)
    self.TipMask:SetActive(false)

    for k,v in pairs(self.BgAdds) do
        bee.addClick(v, function()
            UiManager:showToast(_T("LAB_INFO_045"))
        end)
    end

    bee.addClick(self:find("CloseButton", self.Panel), function()
        self:hideUI()
    end)
    bee.addClick2(self:find("AnimRoot/common_panel_mask_70"), function()
        self:hideUI()
    end)

    bee.addClick(self.TipMask, function()
        self.TipMask:SetActive(false)
    end)

    self.ListAvatar = UiListEx:create(self.AvatarList)
    self.ListAvatar:setWidth(180)
    self.ListAvatar:setRowCount(5)
    self.ListAvatar:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(self.AvatarItem1)
    end)
    self.ListAvatar:setRefreshFunc(function(data, item)
        self:refreshAvatarItem(data, item)
    end)
end

function P:onShow()
    self._datas = CharacterModel:getOwnedCharacters()
    CharacterModel:sortRoles(self._datas)
    self.ListAvatar:setDatas(self._datas)

    local skins = PlayerModel:getFavoriteRoles()
    self._currentSkins = {}
    for k, v in ipairs(skins) do
        self:addCurrentItem(v)
    end
end

function P:addCurrentItem(skinData)
    local item = CU.GameObject.Instantiate(self.CurrentItem1, self.BgAdds[#self._currentSkins + 1].transform, false)
    item:SetActive(true)
    item.transform.localPosition = bee.v3zero
    local r = CharacterModel:getRole(skinData.role)
    if r then
        bee.setText(self:find("TextLevel", item), r:getBondLevelStr())
    else
        bee.setText(self:find("TextLevel", item), CharacterModel:getBondLevelStr(1))
    end
    CharacterModel:setSkinAvater(self:find("Avatar/Mask/ImageIcon", item), skinData.skin_id)
    bee.addClick(item, function()
        Game:playSound("ui_button_confirm")
        Net:sendReq("pb.EditFavoriteRoleREQ", {
            skin_id = skinData.skin_id,
            is_favorite = false,
        })
    end, true)
    table.insert(self._currentSkins, {skin_id = skinData.skin_id, item = item})
end

function P:refreshAvatarItem(data, item)
    bee.setText(self:find("TextLevel", item), data:getBondLevelStr())
    bee.setTextCut(self:find("TextName", item), data:getName(), 150)
    self:find("ImageSelect", item):SetActive(self._selectData == data)
    local skin = self:getFavoriteSkin(data)
    self:find("ImageCheck", item):SetActive(skin ~= nil)
    if skin then
        CharacterModel:setSkinAvater(self:find("Avatar/Mask/ImageIcon", item), skin.id)
    else
        local d = data:getSkinData()
        if d then
            CharacterModel:setSkinAvater(self:find("Avatar/Mask/ImageIcon", item), d.id)
        else
            local defSkin = tpl_character_skin[data:getUsingSkin()]
            if defSkin then
                CharacterModel:setSkinAvater(self:find("Avatar/Mask/ImageIcon", item), defSkin.id)
            end
        end
    end

    bee.addClick(item, function()
        Game:playSound("ui_button_confirm")
        if self._selectData then
            local node = self.ListAvatar:getDataNode(self._selectData)
            if node then
                self:find("ImageSelect", node):SetActive(false)
            end
        end
        self._selectData = data
        self:refreshAvatarItem(data, item)
        local skins = data:getOwnedSkins()
        if #skins > 1 then
            self.TipMask:SetActive(true)
            if self._SkinItems then
                for _, v in ipairs(self._SkinItems) do
                    CU.GameObject.Destroy(v)
                end
            end
            self._SkinItems = {}
            local ImageBg = self:find("ImageBg", self.Tips)
            -- self:removeAllChildren(ImageBg)
            for _, v in ipairs(skins) do
                local skin = CU.GameObject.Instantiate(self.TipItem1, ImageBg.transform, false)
                skin:SetActive(true)
                table.insert(self._SkinItems, skin)
                CharacterModel:setSkinAvater(self:find("Mask/ImageIcon", skin), v.id)

                -- bee.addClick(skin, function()
                --     self.TipMask:SetActive(false)
                -- end)
                bee.addClick(skin, function()
                    Game:playSound("ui_button_confirm")
                    self.TipMask:SetActive(false)
                    if #PlayerModel:getFavoriteRoles() < #self.BgAdds and not self:isRoleSeted(v.id) then
                        Net:sendReq("pb.EditFavoriteRoleREQ", {
                            skin_id = v.id,
                            is_favorite = true,
                        })
                    elseif #PlayerModel:getFavoriteRoles() == #self.BgAdds and not self:isRoleSeted(v.id) then
                        for _, r in ipairs(PlayerModel:getFavoriteRoles()) do
                            if tpl_character_skin[r.skin_id].role == v.role then
                                Net:sendReq("pb.EditFavoriteRoleREQ", {
                                    skin_id = r.skin_id,
                                    is_favorite = false,
                                })
                                Net:sendReq("pb.EditFavoriteRoleREQ", {
                                    skin_id = v.id,
                                    is_favorite = true,
                                })
                                break
                            end
                        end
                    end
                end)
            end
            self.Tips.transform.position = item.transform.position
            local pos = self.Tips.transform.localPosition
            pos.y = pos.y + 120
            self.Tips.transform.localPosition = pos
        else
            if #PlayerModel:getFavoriteRoles() < #self.BgAdds and not self:isRoleSeted(data:getUsingSkin()) then
                Net:sendReq("pb.EditFavoriteRoleREQ", {
                    skin_id = data:getUsingSkin(),
                    is_favorite = true,
                })
            end
        end
    end, true)
end

function P:isRoleSeted(skin_id)
    for _, r in ipairs(PlayerModel:getFavoriteRoles()) do
        if r.skin_id == skin_id then
            return true
        end
    end
    return false
end

function P:refreshUsingItem(data, item)
    bee.setText(self:find("TextLevel", item), data:getBondLevelStr())
    local d = data:getSkinData()
    if d then
        CharacterModel:setSkinAvater(self:find("Avatar/Mask/ImageIcon", item), d.id)
    end
end

function P:getFavoriteSkin(data)
    local skins = PlayerModel:getFavoriteRoles()
    for k, v in ipairs(skins) do
        local d = tpl_character_skin[v.skin_id]
        if d.role == data.role_id then
            return d
        end
    end
    return nil
end

function P:evt_EditFavoriteRoleRSP(msg)
    local skinData = tpl_character_skin[msg.skin_id]
    if msg.is_favorite then
        for _, v in ipairs(self._currentSkins) do
            CU.GameObject.Destroy(v.item)
        end
        local skins = PlayerModel:getFavoriteRoles()
        self._currentSkins = {}
        for k, v in ipairs(skins) do
            self:addCurrentItem(v)
        end
    else
        for k, v in ipairs(self._currentSkins) do
            if v.skin_id == msg.skin_id then
                CU.GameObject.Destroy(v.item)
                for i = k + 1, #self._currentSkins do
                    self._currentSkins[i].item.transform:SetParent(self.BgAdds[i - 1].transform, false)
                end
                table.remove(self._currentSkins, k)
                break
            end
        end
    end
    local r = CharacterModel:getRole(skinData.role)
    local item = self.ListAvatar:getDataNode(r)
    if item then
        self:refreshAvatarItem(r, item)
    end
end

return P