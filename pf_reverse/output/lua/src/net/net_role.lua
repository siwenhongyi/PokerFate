net = net or {}

function net:RoleListRSP(msg)
    CharacterModel:setRoles(msg.role_list)
    CharacterModel.send_gift_cnt = msg.send_gift_cnt
    -- CharacterModel.using_role_id = msg.using_role_id
    CharacterModel:setOwnedSkinIds(msg.owned_skin_ids)
    -- 角色数据返回后再请求装饰方案
    PlayerModel:requestDecorationScheme()

    bee.emit("evt_refreshLobbyRole")
end

function net:RoleRenameRSP(msg)
    if 0 == msg.code then
        local r = CharacterModel:getRole(msg.role_id)
        if r then
            r.name = msg.name
        end
        UiManager:showToast(_T("LAB_CHAR_047"))
    end
end

function net:RoleSetStarRSP(msg)
    if 0 == msg.code then
        local r = CharacterModel:getRole(msg.role_id)
        if r then
            r.is_star = msg.is_star
            UiManager:showToast(msg.is_star and _T("LAB_CHAR_094") or _T("LAB_CHAR_095"))
        end
    end
end

function net:SwitchRoleRSP(msg)
    if 0 == msg.code then
        CharacterModel:setUsingRole(msg.new_role_id)
        UiManager:showToast(_T("LAB_CHAR_104"))
    end
end

function net:SwitchRoleSkinRSP(msg)
    if 0 == msg.code then
        local r = CharacterModel:getRole(msg.role_id)
        if r then
            r:setUsingSkin(msg.new_skin_id)
        end
    end
end

function net:RoleGiftRSP(msg)
    if 0 == msg.code then
        CharacterModel.send_gift_cnt = msg.send_gift_cnt
        local r = CharacterModel:getRole(msg.role_id)
        if r and r.level_info then
            if r.level_info.level < msg.bond_change_rsp.level then
                for i = r.level_info.level, msg.bond_change_rsp.level - 1 do
                    CharacterModel:setRoleLevelUp(msg.role_id, i)
                end
            end
            r.level_info.level = msg.bond_change_rsp.level
            r.level_info.bond_exp = msg.bond_change_rsp.bond_exp
        end
    end
end

function net:RoleBondChangeRSP(msg)
    local r = CharacterModel:getRole(msg.role_id)
    if r then
        r:setBondChange(msg)
    end
end

function net:RoleAwakenRSP(msg)
    if 0 == msg.code then
        local r = CharacterModel:getRole(msg.role_id)
        if r and r.level_info then
            CharacterModel:setRoleLevelUp(msg.role_id, r.level_info.level)
            r.level_info.level = r.level_info.level + 1
        end
        CharacterModel:refreshReddot(CharacterModel._red_role_id)
    end
end

function net:RoleUnlockRSP(msg)
    if CharacterModel:getRoleTotalNum() == 1 then
        CharacterModel:setGetroleguide()
    end
    CharacterModel:addRole(msg.role_info)
    CharacterModel:setNewRole(msg.role_info.role_id)
end

function net:SkinUnlockRSP(msg)
    CharacterModel:addSkin(msg.skin_id)
    CharacterModel:setNewSkin(msg.skin_id)
end

function net:EditFavoriteRoleRSP(msg)
    if not msg.code or 0 == msg.code then
        if msg.is_favorite then
            local roles = PlayerModel:getFavoriteRoles()
            for k, v in ipairs(roles) do
                if tpl_character_skin[v.skin_id].role == tpl_character_skin[msg.skin_id].role then
                    table.remove(roles, k)
                    break
                end
            end
            local role_id = tpl_character_skin[msg.skin_id].role
            local r = CharacterModel:getRole(role_id)
            table.insert(roles, {skin_id = msg.skin_id, bond_level = r and r:getBondLevel() or 1})
        else
            local roles = PlayerModel:getFavoriteRoles()
            for k, v in ipairs(roles) do
                if v.skin_id == msg.skin_id then
                    table.remove(roles, k)
                    break
                end
            end
        end
    end
end