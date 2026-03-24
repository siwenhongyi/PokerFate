local CharacterData = require("app.model.CharacterData")

local P = class("CharacterModel", BaseModel)

local LunarFestival = {
    -- 中秋节
    [1] = {{2026, 9, 25}, {2027, 9, 15}, {2028, 10, 3}},
}

-- 牌手角色系统
function P:ctor(logic)
	self.saveData = {
        cloud = {
            -- files .. uid = {{role_id = id, levels = {level1, level2}}},   -- 档案解锁动画
            -- voices .. uid = {{role_id = id, voices = {"key1", "key2"}}}, -- 声音解锁动画
            -- newroles .. uid = {role_id, role_id},    -- 新角色解锁动画

            -- filereds .. uid = {{role_id = id, levels = {level1, level2}}},   -- 档案红点
            -- filetagreds .. uid = {role_id, role_id},    -- 档案标签红点
            -- voicereds .. uid = {{role_id = id, voices = {"key1", "key2"}}},   -- 声音红点
            -- voicetagreds .. uid = {role_id, role_id},    -- 声音标签红点
            -- newrolereds .. uid = {role_id, role_id},    -- 新角色红点
            -- skinreds .. uid = {skin_id, skin_id},    -- 新皮肤红点
            -- awakenreds .. uid = {role_id, role_id},    -- 可觉醒红点
            -- profilereds .. uid = {role_id, role_id},    -- 角色分析红点
            -- getroleguide .. uid = false,  -- 是否要显示新角色引导
        }
    }

    P.super.ctor(self)
    
    self._roles = {}
    self._owned_skin_ids = {}   -- 已经拥有的皮肤 map
	self._roleMap = {}
    self._defaultRoles = {}
    self.send_gift_cnt = 0  -- 已经送礼次数
    self.using_role_id = 0  -- 当前使用的角色 id

    self._files = nil
    self._voices = nil
    self._newroles = nil
    self._filereds = nil
    self._filetagreds = nil
    self._voicereds = nil
    self._voicetagreds = nil
    self._newrolereds = nil
    self._skinreds = nil
    self._awakenreds = nil
    self._getroleguide = nil
    self._profilereds = nil
end

function P:afterInit()
    for _, v in ipairs(tpl_character_list) do
        table.insert(self._defaultRoles, CharacterData:create({
            role_id = v.id,
            locked = true,
        }))
    end
    table.sort(self._defaultRoles, function(a, b)
        return a.info.sort < b.info.sort
    end)

    self._skin_game_details = nil
end

function P:afterLogin()
    self.send_gift_cnt = 0  -- 已经送礼次数
    self.using_role_id = 0  -- 当前使用的角色 id
    
    self._files = self:getCloudKeyData("files")
    self._filereds = self:getCloudKeyData("filereds")
    self._filetagreds = self:getCloudKeyData("filetagreds")
    self._voices = self:getCloudKeyData("voices")
    self._voicetagreds = self:getCloudKeyData("voicetagreds")
    self._voicereds = self:getCloudKeyData("voicereds")
    self._newroles = self:getCloudKeyData("newroles")
    self._newrolereds = self:getCloudKeyData("newrolereds")
    self._skinreds = self:getCloudKeyData("skinreds")
    self._awakenreds = self:getCloudKeyData("awakenreds")
    self._profilereds = self:getCloudKeyData("profilereds")
    self._getroleguide = self.cloud["getroleguide" .. PlayerModel:getUid()]

    for _, v in ipairs(self._defaultRoles) do
        v:setData({role_id = v.role_id, locked = true})
    end
end

function P:removeNewroleRed(role_id)
    for k, v in ipairs(self._newrolereds) do
        if v == role_id then
            table.remove(self._newrolereds, k)
            self:onSave()
            self:refreshReddot(role_id)
            bee.emit(EventDef.evt_role_newrole_red, role_id)
            return true
        end
    end
    return false
end

function P:removeProfileRed(role_id)
    for k, v in ipairs(self._profilereds) do
        if v == role_id then
            table.remove(self._profilereds, k)
            self:onSave()
            self:refreshReddot(role_id)
            bee.emit(EventDef.evt_role_newrole_red, role_id)
            break
        end
    end
end

function P:isNewFilered(role_id, level)
    if not self._filereds then
        return false
    end
    for k, v in ipairs(self._filereds) do
        if v.role_id == role_id then
            for kk, vv in ipairs(v.levels) do
                if vv == level then
                    return true
                end
            end
            return false
        end
    end
    return false
end

function P:removeFilered(role_id, level)
    for k, v in ipairs(self._filereds) do
        if v.role_id == role_id then
            for kk, vv in ipairs(v.levels) do
                if vv == level then
                    table.remove(v.levels, kk)
                    if #v.levels == 0 then
                        table.remove(self._filereds, k)
                    end
                    self:onSave()
                    self:refreshReddot(role_id)
                    return
                end
            end
            return
        end
    end
end

function P:removeFiletagRed(role_id)
    for k, v in ipairs(self._filetagreds) do
        if v == role_id then
            table.remove(self._filetagreds, k)
            self:onSave()
            self:refreshReddot(role_id)
            break
        end
    end
end

function P:isNewVoicered(role_id, key)
    if not self._voicereds then
        return false
    end
    for k, v in ipairs(self._voicereds) do
        if v.role_id == role_id then
            for kk, vv in ipairs(v.voices) do
                if vv == key then
                    return true
                end
            end
            return false
        end
    end
    return false
end

function P:removeVoicered(role_id, key)
    for k, v in ipairs(self._voicereds) do
        if v.role_id == role_id then
            for kk, vv in ipairs(v.voices) do
                if vv == key then
                    table.remove(v.voices, kk)
                    if #v.voices == 0 then
                        table.remove(self._voicereds, k)
                    end
                    self:onSave()
                    self:refreshReddot(role_id)
                    return
                end
            end
            return
        end
    end
end

function P:removeVoicetagRed(role_id)
    for k, v in ipairs(self._voicetagreds) do
        if v == role_id then
            table.remove(self._voicetagreds, k)
            self:onSave()
            self:refreshReddot(role_id)
            break
        end
    end
end

function P:isRoleHaveNewSkin(role_id)
    if not self._skinreds then
        return false
    end
    for k, v in pairs(self._skinreds) do
        local skin = tpl_character_skin[v]
        if skin and skin.role == role_id then
            return true
        end
    end
    return false
end

function P:isNewSkin(skin_id)
    if not self._skinreds then
        return false
    end
    for k,v in pairs(self._skinreds) do
        if skin_id == v then
            return true
        end
    end
    return false
end

function P:removeSkinRed(skin_id)
    for k, v in ipairs(self._skinreds) do
        if v == skin_id then
            table.remove(self._skinreds, k)
            self:onSave()
            self:refreshReddot(self._red_role_id)
            bee.emit(EventDef.evt_role_newskin_red, skin_id)
            break
        end
    end
end

function P:isRoleCanAwakenRed(role_id)
    if not self._awakenreds then
        return false
    end
    for k, v in pairs(self._awakenreds) do
        if v == role_id then
            local r = self:getRole(role_id)
            if r and r:isCanAwakenRed() then
                return true
            end
            break
        end
    end
    return false
end

function P:removeAwakenRed(role_id)
    for k, v in ipairs(self._awakenreds) do
        if v == role_id then
            table.remove(self._awakenreds, k)
            self:onSave()
            self:refreshReddot(self._red_role_id)
            bee.emit(EventDef.evt_role_awaken_red, role_id)
            break
        end
    end
end

function P:setGetroleguide()
    self._getroleguide = true
    self.cloud["getroleguide" .. PlayerModel:getUid()] = true
    self:onSave()
end

function P:isGetroleguide()
    return self._getroleguide
end

function P:removeGetroleguide()
    self._getroleguide = nil
    self.cloud["getroleguide" .. PlayerModel:getUid()] = nil
    self:onSave()
end

function P:refreshReddot(role_id)
    self._red_role_id = role_id

    local num, roleIds = 0, {}
    local profileNum, skinNum, bondsNum = 0, 0, 0
    
    if self._newrolereds then
        for _, v in ipairs(self._newrolereds) do
            roleIds[v] = v
            -- if v == role_id then
            --     profileNum = profileNum + 1
            -- end
        end
    end
    if self._skinreds then
        for _, v in ipairs(self._skinreds) do
            local skin = tpl_character_skin[v]
            if skin then
                roleIds[skin.role] = v
                if skin.role == role_id then
                    skinNum = skinNum + 1
                end
            end
        end
    end
    if self._profilereds then
        for _, v in ipairs(self._profilereds) do
            -- roleIds[v] = v
            if v == role_id then
                profileNum = profileNum + 1
            end
        end
    end

    -- 可觉醒红点
    if self._awakenreds then
        for _, v in ipairs(self._awakenreds) do
            local r = self:getRole(v)
            if r and r:isCanAwakenRed() then
                if r.role_id == role_id then
                    bondsNum = bondsNum + 1
                end
            end
        end
    end
    
    for _, v in pairs(roleIds) do
        num = num + 1
    end
    RedManager:addTagWithNum(num, RedTag.CharacterMain)
    RedManager:addTagWithNum(profileNum, RedTag.CharacterProfile)
    RedManager:addTagWithNum(skinNum, RedTag.CharacterGarments)
    RedManager:addTagWithNum(bondsNum, RedTag.CharacterBonds)

    local fileTagNum, voiceTagNum = 0, 0
    if role_id then
        for _, v in ipairs(self._filetagreds) do
            if v == role_id then
                fileTagNum = fileTagNum + 1
                break
            end
        end
        for _, v in ipairs(self._voicetagreds) do
            if v == role_id then
                voiceTagNum = voiceTagNum + 1
                break
            end
        end
    end
    RedManager:addTagWithNum(fileTagNum, RedTag.CharacterProfileFiles)
    RedManager:addTagWithNum(voiceTagNum, RedTag.CharacterProfileVoices)

    -- 语音红点
    local voiceNums = {0, 0, 0, 0, 0}
    if role_id and self._voicereds then
        for _, v in ipairs(self._voicereds) do
            if v.role_id == role_id then
                local datas = get_tpl_subKey(tpl_chat_list, "role", role_id)
                for _, vv in ipairs(v.voices) do
                    for _, d in ipairs(datas) do
                        if d.key == vv and d.tag then
                            voiceNums[d.tag] = (voiceNums[d.tag] or 0) + 1
                            break
                        end
                    end
                end
                break
            end
        end
    end
    for k, v in ipairs(voiceNums) do
        RedManager:addTagWithNum(v, RedTag.CharacterProfileVoices .. k)
    end
end

function P:getRole(role_id)
    return self._roleMap[role_id]
end

function P:getCurRole()
    return self._roleMap[self.using_role_id]
end

function P:changeUsingRole(roleId)
    if roleId == self.using_role_id then
        return
    end
    local schemeInfo = PlayerModel:getCurScheme()
    local skin_id = self:getRole(roleId):getSkinData().id
    local property_list = {}
    property_list[1] = PlayerModel.CharacterDefaultPosX * 10
    property_list[2] = PlayerModel.CharacterDefaultPosY * 10
    property_list[3] = PlayerModel.CharacterDefaultPosSize * 100
    property_list[4] = schemeInfo.property_list[4]
    PlayerModel:requestSaveDecorationScheme(schemeInfo.scheme_id, skin_id, schemeInfo.lobby_scene_id, schemeInfo.lobby_bgm_list, property_list, true)
end

function P:changeUsingSkin(skinId)
    local skinCfg = tpl_character_skin[skinId]
    local schemeInfo = PlayerModel:getCurScheme()
    local property_list = schemeInfo.property_list
    if skinCfg.role ~= self:getUsingRoleId() then
        property_list[1] = PlayerModel.CharacterDefaultPosX * 10
        property_list[2] = PlayerModel.CharacterDefaultPosY * 10
        property_list[3] = PlayerModel.CharacterDefaultPosSize * 100
    end
    PlayerModel:requestSaveDecorationScheme(schemeInfo.scheme_id, skinId, schemeInfo.lobby_scene_id, schemeInfo.lobby_bgm_list, schemeInfo.property_list, true)
end

function P:updateUsingRole()
    local schemeInfo = PlayerModel:getCurScheme()
    if schemeInfo then
        local skinCfg = tpl_character_skin[schemeInfo.skin_id]
        local r = self:getRole(skinCfg.role)
        if r then
            -- 切换角色，重新获取语音播放列表
            if skinCfg.role ~= self.using_role_id then
                self._sound_index = 0
            end
            r:setUsingSkin(schemeInfo.skin_id)
        end
        self:setUsingRole(skinCfg.role)
    end
end

function P:setUsingRole(role_id)
    self.using_role_id = role_id
end

function P:getUsingRoleId()
    if 0 ~= self.using_role_id then
        return self.using_role_id
    end
    return tpl_character_list[1].id
end

function P:getUsingRole()
    return self._roleMap[self.using_role_id]
end

function P:setRoles(roles)
	self._roles = {}
	self._roleMap = {}
	for _, v in ipairs(roles) do
        self:addRole(v)
	end

    self:refreshReddot()
end

function P:getRoleName(roleId)
    local r = self:getRole(roleId)
    if r then
        return r:getName()
    end
    return _T(tpl_character[roleId].name)
end

-- 获取剩余送礼次数
function P:getLeftGiftCnt()
    local ret = VipModel:getDailyGiftCounts() - self.send_gift_cnt
    if ret < 0 then ret = 0 end
    return ret
end

function P:setOwnedSkinIds(skins)
    self._owned_skin_ids = {}
    for _, v in ipairs(skins) do
        self._owned_skin_ids[v] = v
    end
end

function P:addRole(role)
    local r = self:getRoleData(role.role_id)
    if not r then
        r = CharacterData:create(role)
    else
        r:setData(role)
    end
    table.insert(self._roles, r)
    self._roleMap[role.role_id] = r
end

function P:sortRoles(datas)
    table.sort(datas, function(a, b)
        if a.role_id == self.using_role_id or b.role_id == self.using_role_id then
            return a.role_id == self.using_role_id
        end
        if a.is_star ~= b.is_star then
            return a.is_star
        end
        if a:getBondLevel() ~= b:getBondLevel() then
            return a:getBondLevel() > b:getBondLevel()
        end
        return a.info.sort < b.info.sort
    end)
end

function P:getAllCharacters()
    local datas = self:getOwnedCharacters()
    
    for _, v in ipairs(self._defaultRoles) do
        if not self._roleMap[v.role_id] then
            if not v.info.display_time or v.info.display_time <= bee.getServerTime() then
                table.insert(datas, v)
            elseif bee.isDev or PlayerModel:isEventWhite() then
                table.insert(datas, v)
            end
        end
    end
    return datas
end

function P:getOwnedCharacters()
    local datas = {}
    for _, v in ipairs(self._roles) do
        table.insert(datas, v)
    end
    self:sortRoles(datas)
    return datas
end

function P:getStarredCharacters()
    local datas = {}
    for _, v in ipairs(self._roles) do
        if v.is_star then
            table.insert(datas, v)
        end
    end
    self:sortRoles(datas)
    return datas
end

function P:addSkin(skin_id)
    self._owned_skin_ids[skin_id] = skin_id
    local d = tpl_character_skin[skin_id]
    if d then
        local r = CharacterModel:getRole(d.role)
        if r then
            r:addSkin(skin_id)
        end
    end
end

function P:setSkinAvater(iconNode, skin_id)
    local d = tpl_character_skin[skin_id]
    if d then
        d = tpl_props[d.avatar]
        if d then
            bee.setIcon(iconNode, d.icon)
        end
    end
end

function P:isOwnedSkin(skin_id)
    return self._owned_skin_ids[skin_id] ~= nil
end

-- 是否只有皮肤而没有角色
function P:isOwnedSkinAndNoRole(skin_id)
    return self._owned_skin_ids[skin_id] ~= nil and nil == self:getRole(tpl_character_skin[skin_id].role)
end

-- 是否需要播放档案解锁动画
function P:isPlayFileAnim(role_id, index)
    for k, v in ipairs(self._files) do
        if v.role_id == role_id then
            for kk, vv in ipairs(v.levels) do
                if vv == index then
                    table.remove(v.levels, kk)
                    if #v.levels == 0 then
                        table.remove(self._files, k)
                    end
                    self:onSave()
                    return true
                end
            end
            return false
        end
    end
    return false
end

-- 是否需要播放声音解锁动画
function P:isPlayVoiceAnim(role_id, key)
    for k, v in ipairs(self._voices) do
        if v.role_id == role_id then
            for kk, vv in ipairs(v.voices) do
                if vv == key then
                    table.remove(v.voices, kk)
                    if #v.voices == 0 then
                        table.remove(self._voices, k)
                    end
                    self:onSave()
                    return true
                end
            end
            return false
        end
    end
    return false
end

-- 是否需要播放角色解锁动画
function P:isPlayNewRoleAnim(role_id)
    for k, v in ipairs(self._newroles) do
        if v == role_id then
            table.remove(self._newroles, k)
            self:onSave()
            return true
        end
    end
    return false
end

function P:setRoleLevelUp(role_id, level)
    local fd = table.getValue(self._files, "role_id", role_id)
    if fd then
        table.insert(fd.levels, level)
    else
        table.insert(self._files, {role_id = role_id, levels = {level}})
    end
    fd = table.getValue(self._filereds, "role_id", role_id)
    if fd then
        table.insert(fd.levels, level)
    else
        table.insert(self._filereds, {role_id = role_id, levels = {level}})
    end

    table.addValue(self._filetagreds, role_id)

    local vs = {}
    local ds = get_tpl_subKey(tpl_chat_list, "role", role_id)
    for _, v in ipairs(ds) do
        if v.unlock == level + 1 then
            table.insert(vs, v.key)
        end
    end
    if #vs > 0 then
        local vd = table.getValue(self._voices, "role_id", role_id)
        if not vd then
            vd = {role_id = role_id, voices = {}}
            table.insert(self._voices, vd)
        end
        table.append(vd.voices, vs)

        vd = table.getValue(self._voicereds, "role_id", role_id)
        if not vd then
            vd = {role_id = role_id, voices = {}}
            table.insert(self._voicereds, vd)
        end
        table.append(vd.voices, vs)

        table.addValue(self._voicetagreds, role_id)
    end

    if level + 1 == Config.AWAKEN_LEVEL then
        table.addValue(self._awakenreds, role_id)
    end

    self:onSave()
    self:refreshReddot(self._red_role_id)

    bee.emit(EventDef.evt_role_role_red, role_id)
end

function P:setNewRole(role_id)
    table.addValue(self._newroles, role_id)
    table.addValue(self._newrolereds, role_id)
    table.addValue(self._profilereds, role_id)
    self:onSave()
    self._isGetRewRole = true
    self:refreshReddot(self._red_role_id)
end

function P:setNewSkin(skin_id)
    local skinData = tpl_character_skin[skin_id]
    if skinData and skinData.kind ~= SKIN_KIND.NORMAL and skinData.kind ~= SKIN_KIND.AWAKEN then
        table.addValue(self._skinreds, skin_id)
        self:onSave()
        self:refreshReddot(self._red_role_id)
    end
end

function P:isHaveNewRole()
    return self._newroles and #self._newroles > 0
end

function P:isNewRole(role_id)
    if not self._newrolereds then
        return false
    end
    for k,v in pairs(self._newrolereds) do
        if role_id == v then
            return true
        end
    end
    return false
end

function P:isGetNewRole()
    local ret = self._isGetRewRole
    self._isGetRewRole = false
    return ret
end

-- 获取角色当前使用的皮肤
function P:getRoleSkinData(role_id)
    local r = self:getRole(role_id)
    if r then
        return r:getSkinData()
    end
    
    local skins = get_tpl_subKey(tpl_character_skin_list, "role", role_id)
    if skins and #skins > 0 then
        return skins[1]
    end
    return nil
end

function P:getRoleTotalNum()
    return #self._roles
end

function P:getSkinTotalNum()
    local ret = 0
    for _, v in ipairs(self._roles) do
        ret = ret + #v:getOwnedSkins()
    end
    return ret
end

function P:getBondLevelStr(lvl, text)
    if lvl < 6 then
        return "Lv." .. lvl
    end
    return _T(text or "LAB_CHAR_041")
end

function P:getRoleData(id)
    local role = CharacterModel:getRole(id)
    if not role then
        for _, v in ipairs(self._defaultRoles) do
            if v.role_id == id then
                role = v
                break
            end
        end
    end
    return role
end

-- 是否已拥有该角色
function P:getRoleIsOwn(id)
    return self:getRole(id) ~= nil
end

-- 获取角色的语音配置列表
function P:getChats(kind, role_id)
    role_id = role_id or self.using_role_id
    local datas = get_tpl_subKey(tpl_chat_list, "role", role_id)
    if datas then
        local rets = {}
        for _, v in ipairs(datas) do
            if v.kind == kind then
                table.insert(rets, v)
            end
        end
        return rets
    end
    return nil
end

function P:getRoleImage(name)
    if not self._roleImages then
        self._roleImages = {}
    end
    name = name or "Main"
    if not bee.isNull(self._roleImages[name]) then
        return self._roleImages[name]
    end
    self._roleImages[name] = bee.createObj("views/Character/CharacterImage")
    return self._roleImages[name]
end

function P:getRoleCanvas(name)
    return UiManager:showUI("CharacterRoleCanvas", {parent = bee.find("UIRoot"), multi = true})
end

-- 获取角色好感度等级对应的奖励 id 列表
function P:getRoleBondsRewards(role_id, lvl)
    local rewards = {}
    local bonds = get_tpl_subKey(tpl_character_bond_list, "role", role_id)
    if bonds then
        for _, v in ipairs(bonds) do
            if v.level + 1 == lvl and v.awaken_rewards then
                for _, vv in ipairs(v.awaken_rewards) do
                    table.insert(rewards, vv)
                end
            end
        end
        table.sort(rewards, function(a, b)
            local t1, t2 = tpl_props[a].type, tpl_props[b].type
            if t1 == GPropKind.Avatar then
                return true
            elseif t2 == GPropKind.Avatar then
                return false
            end
            if t1 == GPropKind.Title then
                return true
            elseif t2 == GPropKind.Title then
                return false
            end
            return a < b
        end)
    end

    local emojis = get_tpl_subKey(tpl_emoji_list, "role", role_id)
    if emojis then
        for _, v in ipairs(emojis) do
            if v.unlock == lvl then
                table.insert(rewards, GPropId.CharacterEmojiId)   -- 表情奖励 id
                break
            end
        end
    end
    
    local ds = get_tpl_subKey(tpl_chat_list, "role", role_id)
    if ds then
        for _, v in ipairs(ds) do
            if v.unlock == lvl then
                table.insert(rewards, GPropId["CharacterVoiceId" .. lvl])   -- 语音奖励 id
                break
            end
        end
    end

    if lvl > 1 then
        local bonds = get_tpl_subKey(tpl_character_bond_list, "role", role_id)
        if bonds and bonds[1].archive_name then
            table.insert(rewards, GPropId["CharacterFileId" .. (lvl - 1)])   -- 档案奖励 id
        end
    end

    return rewards
end

function P:evt_serverTimeCrossDay()
    self.send_gift_cnt = 0
end

function P:requestGetSkinGameDetail()
    Net:sendReq("pb.GetSkinGameDetailREQ", {})
end

function P:evt_GetSkinGameDetailRSP(msg)
    self._skin_game_details = msg.skin_game_details
end

function P:getRoleSkinGameDetails(skinId)
    if not self._skin_game_details then
        return 0
    end
    for k,v in pairs(self._skin_game_details) do
        if v.skin_id == skinId then
            return v.game_cnt
        end
    end
    return 0
end

function P:getCurSeason()
    local month = os.date("!*t", bee.getServerTime()).month
    if month >= 3 and month <= 5 then
        return 1
    elseif month >= 6 and month <= 8 then
        return 2
    elseif month >= 9 and month <= 11 then
        return 3
    else
        return 4
    end
end

function P:_isInFestival(id)
    id = tonumber(id)
    -- 节日问候语使用本地时间
    local curDate = os.date("*t", os.time())
    if id == 1 then -- 元旦
        return curDate.month == 1 and curDate.day == 1
    elseif id == 2 then -- 情人节
        return curDate.month == 2 and curDate.day == 14
    elseif id == 3 then -- 愚人节
        return curDate.month == 4 and curDate.day == 1
    elseif id == 4 then -- 七夕节
        return curDate.month == 7 and curDate.day == 7
    elseif id == 5 then -- 圣诞节
        return curDate.month == 12 and curDate.day == 25
    elseif id == 6 then -- 万圣节
        return curDate.month == 11 and curDate.day == 1
    end
end

function P:_isInLunarFestival(id)
    id = tonumber(id)

    -- -- 计算农历时间有问题，跟整包修改
    -- local m, d = TimeHelp:getLunarMonthAndDay(os.time())
    -- if id == 1 then -- 中秋节
    --     return m == 8 and d == 15
    -- end

    local curDate = os.date("*t", os.time())
    local lunarList = LunarFestival[id]
    if lunarList then
        for k,v in pairs(lunarList) do
            if v[1] == curDate.year then
                return curDate.month == v[2] and curDate.day == v[3]
            end
        end
    end
end

function P:getCharacterChatList(skin_id)
    local skinCfg = tpl_character_skin[skin_id]
    local character_sound_list = {}
    if not skinCfg then
        return character_sound_list
    end
    -- 节日语音
    if skinCfg.festival_voice then
        for i = 1, #skinCfg.festival_voice, 4 do
            if self:_isInFestival(skinCfg.festival_voice[i]) then
                table.insert(character_sound_list, {sound = skinCfg.festival_voice[i + 1], face = skinCfg.festival_voice[i + 2], text = skinCfg.festival_voice[i + 3]})
            end
        end
    end
    if skinCfg.lunar_calendar_voice then
        for i = 1, #skinCfg.lunar_calendar_voice, 4 do
            if self:_isInLunarFestival(skinCfg.lunar_calendar_voice[i]) then
                table.insert(character_sound_list, {sound = skinCfg.lunar_calendar_voice[i + 1], face = skinCfg.lunar_calendar_voice[i + 2], text = skinCfg.lunar_calendar_voice[i + 3]})
            end
        end
    end
    -- 活动语音
    if skinCfg.new_activity_voice then
        for i = 1, #skinCfg.new_activity_voice, 4 do
            if ActivityManager:isActivityOpen(ActivityId.Theme, tonumber(skinCfg.new_activity_voice[i])) then
                table.insert(character_sound_list, {sound = skinCfg.new_activity_voice[i + 1], face = skinCfg.new_activity_voice[i + 2], text = skinCfg.new_activity_voice[i + 3]})
            end
        end
    end
    -- 原皮语音
    if skinCfg.default_click_voice then
        for i = 1, #skinCfg.default_click_voice, 3 do
            table.insert(character_sound_list, {sound = skinCfg.default_click_voice[i], face = skinCfg.default_click_voice[i + 1], text = skinCfg.default_click_voice[i + 2]})
        end
    end
    -- 觉醒语音
    if skinCfg.awakened_click_voice then
        local role = self:getRole(skinCfg.role)
        if role:isAwaken() then
            for i = 1, #skinCfg.awakened_click_voice, 3 do
                table.insert(character_sound_list, {sound = skinCfg.awakened_click_voice[i], face = skinCfg.awakened_click_voice[i + 1], text = skinCfg.awakened_click_voice[i + 2]})
            end
        end
    end
    -- 季节问候语音
    if skinCfg.season_voice then
        local curSeason = tostring(self:getCurSeason())
        for i = 1, #skinCfg.season_voice, 4 do
            if curSeason == skinCfg.season_voice[i] then
                table.insert(character_sound_list, {sound = skinCfg.season_voice[i + 1], face = skinCfg.season_voice[i + 2], text = skinCfg.season_voice[i + 3]})
            end
        end
    end

    return character_sound_list
end

function P:getCharacterSound()
    -- 每次刷新语音的时候刷新一下播放列表
    local schemeInfo = PlayerModel:getCurScheme()
    local skinId = schemeInfo.skin_id
    self._character_sound_list = self:getCharacterChatList(skinId)
    self._max_sound_count = #self._character_sound_list

    -- 播放下一句
    if not self._sound_index then
        self._sound_index = 0
    end
    self._sound_index = self._sound_index + 1
    if self._sound_index > self._max_sound_count then
        self._sound_index = 1
    end
    return self._character_sound_list[self._sound_index]
end

