local CharacterData = require("app.model.CharacterData")

local P = class("CharacterModel", BaseModel)

local LunarFestival = {
    -- 中秋节 (农历八月十五)
    [1] = {{2026, 9, 25}, {2027, 9, 15}, {2028, 10, 3}, {2029, 9, 22}, {2030, 9, 12},
           {2031, 10, 1}, {2032, 9, 19}, {2033, 9, 8}, {2034, 9, 27}, {2035, 9, 16},
           {2036, 10, 4}, {2037, 9, 24}, {2038, 9, 13}, {2039, 10, 2}, {2040, 9, 20},
           {2041, 9, 10}, {2042, 9, 28}, {2043, 9, 17}, {2044, 10, 5}, {2045, 9, 25},
           {2046, 9, 15}, {2047, 10, 4}, {2048, 9, 22}, {2049, 9, 11}, {2050, 9, 30}},
    -- 七夕 (农历七月初七, 基于19年Metonic周期推算)
    [4] = {{2026, 8, 19}, {2027, 8, 8}, {2028, 8, 26}, {2029, 8, 16}, {2030, 8, 5},
           {2031, 8, 24}, {2032, 8, 12}, {2033, 8, 1}, {2034, 8, 20}, {2035, 8, 10},
           {2036, 8, 28}, {2037, 8, 17}, {2038, 8, 7}, {2039, 8, 25}, {2040, 8, 14},
           {2041, 8, 4}, {2042, 8, 22}, {2043, 8, 10}, {2044, 8, 29}, {2045, 8, 19},
           {2046, 8, 8}, {2047, 8, 26}, {2048, 8, 16}, {2049, 8, 5}, {2050, 8, 24}},
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
    self._storys = nil
    self._openedStorys = nil
    self._secondAwakenNew = nil
    self._waitSecondAwaken = {}

    self.unlockStoryList = {}
    self.openedStoryList = {}
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
    self._storys = self:getCloudKeyData("storys")
    self._openedStorys = self:getCloudKeyData("openedStorys")
    self._getroleguide = self.cloud["getroleguide" .. PlayerModel:getUid()]
    self._secondAwakenNew = self:getCloudKeyData("secondawakennew")

    for _, v in ipairs(self._defaultRoles) do
        v:setData({role_id = v.role_id, locked = true})
    end

    self._roleTaskList = {}
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
    local exchange = self:saveOpenedStory(role_id)
    for k, v in ipairs(self._filetagreds) do
        if v == role_id then
            table.remove(self._filetagreds, k)
            exchange = true
            break
        end
    end

    if exchange then
        self:onSave()
        self:refreshReddot(role_id)
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

function P:isRoleSecondAwakenNewRed(role_id)
    for k,v in pairs(self._secondAwakenNew) do
        if v == role_id then
            return true
        end
    end
    return false
end

function P:removeSecondAwakenNewRed(role_id)
    for k, v in ipairs(self._secondAwakenNew) do
        if v == role_id then
            table.remove(self._secondAwakenNew, k)
            self:onSave()
            self:refreshReddot(role_id)
            bee.emit(EventDef.evt_role_role_red, role_id)
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

    if self._secondAwakenNew then
        for _, v in ipairs(self._secondAwakenNew) do
            local r = self:getRole(v)
            if r.role_id == role_id then
                roleIds[v] = v
            end
        end
    end
    if self._waitSecondAwaken[role_id] and self._waitSecondAwaken[role_id] == 1 then
        roleIds[role_id] = role_id
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
        if self._openedStorys then
            if self:checkNewOpened(role_id) then
                fileTagNum = fileTagNum + 1
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

-- function P:changeUsingRole(roleId)
--     if roleId == self.using_role_id then
--         return
--     end
--     local schemeInfo = DecorationModel:getCurScheme()
--     local skin_id = self:getRole(roleId):getSkinData().id
--     local property_list = {}
--     property_list[1] = PlayerModel.CharacterDefaultPosX * 10
--     property_list[2] = PlayerModel.CharacterDefaultPosY * 10
--     property_list[3] = PlayerModel.CharacterDefaultPosSize * 100
--     property_list[4] = schemeInfo.property_list[4]
--     property_list[5] = schemeInfo.property_list[5]
--     DecorationModel:requestSaveDecorationScheme(
--         schemeInfo.scheme_id, skin_id, schemeInfo.lobby_scene_id, schemeInfo.lobby_bgm_list, schemeInfo.avatar, schemeInfo.frame, schemeInfo.title, property_list, true)
-- end

-- function P:changeUsingSkin(skinId)
--     local skinCfg = tpl_character_skin[skinId]
--     local schemeInfo = DecorationModel:getCurScheme()
--     local property_list = schemeInfo.property_list
--     if skinCfg.role ~= self:getUsingRoleId() then
--         property_list[1] = PlayerModel.CharacterDefaultPosX * 10
--         property_list[2] = PlayerModel.CharacterDefaultPosY * 10
--         property_list[3] = PlayerModel.CharacterDefaultPosSize * 100
--         property_list[5] = 0
--     end
--     DecorationModel:requestSaveDecorationScheme(
--         schemeInfo.scheme_id, skinId, schemeInfo.lobby_scene_id, schemeInfo.lobby_bgm_list, schemeInfo.avatar, schemeInfo.frame, schemeInfo.title, schemeInfo.property_list, true)
-- end

function P:updateUsingRole()
    local schemeInfo = DecorationModel:getCurScheme()
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
    return self._roleMap[self:getUsingRoleId()]
end
function P:getUsingRoleSkin()
    local scheme = bee.isInGame() and DecorationModel:getInGameCurScheme() or DecorationModel:getCurScheme()
    local skinId = scheme.skin_id
    return tpl_character_skin[skinId]
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
    local isRandom = DecorationModel:isInGameSchemeRandom()
    for _, v in ipairs(datas) do
        v.__is_in_user = DecorationModel:checkRoleInScheme(SchemeTag.Ingame, not isRandom, v.role_id)
    end
    table.sort(datas, function(a, b)
        if a.__is_in_user ~= b.__is_in_user then
            return a.__is_in_user
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
    self:_addVoiceTags(vs, role_id)

    if level + 1 == Config.AWAKEN_LEVEL then
        table.addValue(self._awakenreds, role_id)
    end
    
    if level == Config.AWAKEN_LEVEL then
        local role = self:getRole(role_id)
        if role:isCanSecondAwaken() then
            table.addValue(self._secondAwakenNew, role_id)
            self:onSave()
        end
    elseif level == Config.SECOND_AWAKEN_LEVEL then
        self._waitSecondAwaken[role_id] = nil
    end

    self:onSave()
    self:refreshReddot(self._red_role_id)

    bee.emit(EventDef.evt_role_role_red, role_id)
end

function P:_addVoiceTags(vs, role_id)
    if vs and #vs > 0 then
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

    if skinData then
        local role_id = skinData.role
        local vs = {}
        local ds = get_tpl_subKey(tpl_chat_list, "role", role_id)
        for _, v in ipairs(ds) do
            if v.skin_voice == skin_id then
                table.insert(vs, v.key)
            end
        end
        self:_addVoiceTags(vs, role_id)
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

-- 获取皮肤专用语音
function P:getSkinChatData(skin_id, kind)
    local skin = tpl_character_skin[skin_id]
    if skin then
        local ds = get_tpl_subKey(tpl_chat_list, "role", skin.role)
        for _, v in ipairs(ds) do
            if v.skin_voice == skin_id and v.kind == kind then
                return v
            end
        end
    end
    return nil
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
        if LAN:getLanguage() == "jp" then
            return curDate.month == 7 and curDate.day == 7
        else
            return self:_isInLunarFestival(id)
        end
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
    -- 二次觉醒语音
    if skinCfg.awakened2_click_voice then
        local role = self:getRole(skinCfg.role)
        if role:isSecondAwaken() then
            for i = 1, #skinCfg.awakened2_click_voice, 3 do
                table.insert(character_sound_list, {sound = skinCfg.awakened2_click_voice[i], face = skinCfg.awakened2_click_voice[i + 1], text = skinCfg.awakened2_click_voice[i + 2]})
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
    local schemeInfo = DecorationModel:getCurScheme()
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


-- ================================= 二次誓约任务 =================================

-- 获取所有可二次觉醒角色的任务
function P:reqAllTaskList()
    for k, v in pairs(self._roles) do
        self:reqRoleTaskList(v.role_id)
    end
end

-- 获取角色二次觉醒任务
function P:reqRoleTaskList(role_id)
    if not role_id then
        return
    end

    local role = self:getRole(role_id)
    if not role then
        bee.emit("evt_updateCharacterTask", {role_id = role_id})
        return
    end
    if not role:isCanSecondAwaken() then
        return
    end
    if role:isSecondAwaken() then
        return
    end

    Net:post("task/roleTaskList", {role_id = role_id}, function(data)
        if data.code ~= 0 then
            return
        end
        self._roleTaskList[role_id] = data.list

        local isComplete = true
        for k,v in pairs(data.list) do
            if v.status ~= TaskStatus.Completed then
                isComplete = false
                break
            end
        end
        if isComplete and not self:getRole(role_id):isSecondAwaken() then
            self._waitSecondAwaken[role_id] = 1
        else
            self._waitSecondAwaken[role_id] = nil
        end
        self:refreshReddot(role_id)
        bee.emit("evt_updateCharacterTask")
    end)
end

function P:getRoleTaskList(role_id)
    local list = self._roleTaskList[role_id]
    if list then
        table.sort(list, function(a, b)
            local sumA = 100
            local sumB = 100
            if a.status == TaskStatus.InProgress then
                sumA = sumA + 10
            end
            if b.status == TaskStatus.InProgress then
                sumB = sumB + 10
            end
            if a.sort < b.sort then
                sumA = sumA + 1
            end
            if b.sort < a.sort then
                sumB = sumB + 1
            end
            return sumA > sumB
        end)
        return self._roleTaskList[role_id]
    else
        local roleCfg = tpl_character[role_id]
        if not roleCfg.tasks then
            return {}
        end
        local list = get_tpl_subKey(tpl_character_task_list, "group", roleCfg.tasks)
        table.sort(list, function(a, b) return a.sort < b.sort end)
        return list
    end
end

function P:reqRecRoleTaskRw(role, succCb)
    if not role then
        return
    end
    
    if not role:isAwaken() or role:isSecondAwaken() then
        return
    end

    Net:post("task/recRoleTaskRw", {role_id = role.role_id}, function(data)
        if data.code ~= 0 then
            return
        end
        if succCb then
            succCb()
        end
        role.level_info.level = Config.SECOND_AWAKEN_LEVEL
        self:setRoleLevelUp(role.role_id, Config.SECOND_AWAKEN_LEVEL)
    end)
end

function P:evt_NoticeBRC(params)
    if params.type == tpl_PushConsts.ROLE_TASK_REFRESH.code then
        self:reqAllTaskList()
    end
end

function P:isWaitSecondAwaken(role_id)
    if not self._waitSecondAwaken then
        return false
    end
    return self._waitSecondAwaken[role_id] == 1
end

-- =============================== 角色剧情 ===============================

--获取角色剧情数据
function P:getRoleThemeStory()
    Net:post("activity/themeStory", nil, function (data)
        if data.code ~= 0 then
            return
        end
        self.unlockStoryList = data.id_arr or {}
    end)
end

--解锁角色剧情
function P:reqUnlockRoleStory(id)
    -- table.insert(self.unlockStoryList, id)
    -- bee.emit("evt_UnlockStoryCallback", {id = id})
    Net:post("activity/unlockThemeStory", {id = id}, function (data)
        if data.code ~= 0 then
            return
        end
        table.insert(self.unlockStoryList, id)
        bee.emit("evt_UnlockStoryCallback", {id = id})
    end)
end

--开放的角色剧情
function P:getOpenedStory()
    self.openedStoryList = {}
    
    local inThemeing, curThemeId, overThemeId = self:getThemeData()
    for _,v in pairs(tpl_theme_storys) do
        if (not inThemeing and v.group <= overThemeId) or (inThemeing and v.group < curThemeId) then
            table.insert(self.openedStoryList, v.id)
        end
    end
end

--是否有新增开放的角色剧情
function P:checkNewOpened(id)
    if id == nil or id == 0 then
        return false
    end
    local inThemeing, curThemeId, overThemeId = self:getThemeData()
    local roleCfg = tpl_character[id]
    if roleCfg.plot_review then
        local reviewCount = #roleCfg.plot_review
        for i = 1, reviewCount, 2 do
            local themeId = roleCfg.plot_review[i]
            local storyId = roleCfg.plot_review[i + 1]
            if (not inThemeing and themeId <= overThemeId) or (inThemeing and themeId < curThemeId) then
                if table.keyof(self._openedStorys, storyId) == nil then
                    return true
                end
            end
        end
    end
    return false
end
--记录开放的角色剧情
function P:saveOpenedStory(id)
    local exchange = false
    if id == nil or id == 0 then
        return exchange
    end
    local inThemeing, curThemeId, overThemeId = self:getThemeData()
    local roleCfg = tpl_character[id]
    if roleCfg.plot_review then
        local reviewCount = #roleCfg.plot_review
        for i = 1, reviewCount, 2 do
            local themeId = roleCfg.plot_review[i]
            local storyId = roleCfg.plot_review[i + 1]
            if (not inThemeing and themeId <= overThemeId) or (inThemeing and themeId < curThemeId) then
                if table.keyof(self._openedStorys, storyId) == nil then
                    table.insert(self._openedStorys, storyId)
                    exchange = true
                end
            end
        end
    end
    return exchange
end

--活动信息
function P:getThemeData()
    local curThemeId = ThemeModel:getConfId()
    local themeCfg = tpl_theme_activity[curThemeId]
    local ct = bee.getServerTime()
    local inThemeing = false
    --是否在活动中
    if ct > themeCfg.time_start and ct < themeCfg.time_end then
        inThemeing = true
    end
    --最后结束的活动
    local overThemeId = 0
    if not inThemeing then
        for _,v in pairs(tpl_theme_activity) do
            if ct > v.time_start and ct > v.time_end then
                if v.id > overThemeId then
                    overThemeId = v.id
                end
            end
        end
    end
    return inThemeing, curThemeId, overThemeId
end

--剧情是否开放
function P:checkStoryOpened(id)
    return table.keyof(self.openedStoryList, id) ~= nil
end

--剧情是否解锁
function P:checkStoryUnlock(id)
    return table.keyof(self.unlockStoryList, id) ~= nil
end

--新剧情判定
function P:isNewStory(id)
    return table.keyof(self._storys, id) == nil
end

--剧情观看记录
function P:saveStory(id)
    table.insert(self._storys, id)
    self:onSave()
    self:refreshReddot(self._red_role_id)
end


return P