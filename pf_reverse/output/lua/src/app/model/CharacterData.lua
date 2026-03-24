local P = class("CharacterData")

function P:ctor(data)
    self:setData(data)
end

function P:setData(data)
    self.role_id = data.role_id
    self.skin_info = data.skin_info
    self.level_info = data.level_info
    self.name = data.name
    self.is_star = data.is_star

    self.locked = data.locked

    self.info = tpl_character[self.role_id]
end

function P:getName()
    if self.name and self.name ~= "" then
        return self.name
    end
    return _T(self.info.name)
end

function P:isAwaken()
    return self:getBondLevel() == Config.AWAKEN_LEVEL + 1
end

function P:isCanAwaken()
    return self:getBondLevel() == Config.AWAKEN_LEVEL
end

function P:getBondLevel()
    if self.level_info then
        return self.level_info.level
    end
    return 0
end

function P:getBondLevelStr(text)
    local lvl = self:getBondLevel()
    return CharacterModel:getBondLevelStr(lvl, text)
end

function P:getBondExp()
    if self.level_info then
        return self.level_info.bond_exp
    end
    return 0
end

function P:getUsingSkin()
    if self.skin_info then
        return self.skin_info.skin_id
    end
    return 0
end

function P:addSkin(skin_id)
    if self.skin_info then
        table.insert(self.skin_info.owned_skin_ids, skin_id)
    end
end

function P:isOwnedSkin(skin_id)
    if self.skin_info then
        for _, v in ipairs(self.skin_info.owned_skin_ids) do
            if v == skin_id then
                return true
            end
        end
    end
    return CharacterModel:isOwnedSkin(skin_id)
end

function P:getOwnedSkins()
    local skins = {}
    if self.skin_info then
        for _, v in ipairs(self.skin_info.owned_skin_ids) do
            table.insert(skins, tpl_character_skin[v])
        end
    end
    return skins
end

function P:setUsingSkin(skin_id)
    if self.skin_info then
        self.skin_info.skin_id = skin_id
    end
end

function P:getAwakenSkinData()
    local skins = get_tpl_subKey(tpl_character_skin_list, "role", self.role_id)
    if skins and #skins > 0 then
        for _, v in ipairs(skins) do
            if v.kind == SKIN_KIND.AWAKEN then
                return v
            end
        end
    end
    return nil
end

function P:getSkinData()
    if self.skin_info and tpl_character_skin[self.skin_info.skin_id] then
        return tpl_character_skin[self.skin_info.skin_id]
    end
    local skins = get_tpl_subKey(tpl_character_skin_list, "role", self.role_id)
    if skins and #skins > 0 then
        return skins[1]
    end
    return nil
end

function P:getDefaultSkinData()
    local skins = get_tpl_subKey(tpl_character_skin_list, "role", self.role_id)
    if skins and #skins > 0 then
        return skins[1]
    end
    return nil
end

function P:getSkinImage()
    local d = self:getSkinData()
    if d then
        return d.image
    end
    return ""
end

function P:getSkinImageWithBg()
    local d = self:getSkinData()
    if d then
        return d.image_with_bg or d.image
    end
    return ""
end

function P:setSkinImageOffset(ImageIcon, name, originalPos)
    local d = self:getSkinData()
    if d and d[name] then
        local pos = originalPos or ImageIcon.transform.localPosition
        pos.x, pos.y = pos.x + d[name][1], pos.y + d[name][2]
        ImageIcon.transform.localPosition = pos
    end
end

function P:setBondChange(d)
    self.level_info.level = d.level
    self.level_info.bond_exp = d.bond_exp
end

function P:getAwakenItems()
    local datas = get_tpl_subKey(tpl_character_bond_list, "role", self.role_id)
    for _, v in ipairs(datas) do
        if v.awaken then
            return v.awaken
        end
    end
    return nil
end

-- 是否满足觉醒条件
function P:isCanAwakenRed()
    if self:isCanAwaken() then
        local items = self:getAwakenItems()
        if items then
            for i = 1, #items - 1, 2 do
                if ItemModel:getItemNumById(items[i]) < items[i + 1] then
                    return false
                end
            end
            return true
        end
    end
    return false
end

return P
