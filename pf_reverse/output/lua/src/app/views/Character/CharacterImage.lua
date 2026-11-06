local P = class("CharacterImage", Object)

function P:onAwake()
    self.ImageRole = self:find("ImageRole")
    self.RoleSpine = self:find("RoleSpine")
    self.EffTip = self:find("EffTip")
    if self.EffTip then
        self.EffTip:SetActive(false)
    end
    self._effShowFlag = true

    self._roleAnim = nil
end

function P:setShowReal(flag)
    self._showReal = flag
end

function P:setShowInMask(flag)
    if self._roleSpine then
        local Mask = bee.find("Mask", self._roleSpine)
        if Mask then
            Mask:SetActive(true)
            local Image = bee.find("Image", self._roleSpine)
            local Spine = bee.find("Spine", self._roleSpine)
            local ImageFg = bee.find("ImageFg", self._roleSpine)
            Image.transform:SetParent(Mask.transform)
            Spine.transform:SetParent(Mask.transform)
            ImageFg.transform:SetParent(Mask.transform)
        end
    end
end

-- 初始化交互
function P:initSpecialInteraction(callback)
    local cfg = self._skinData
    if not cfg.special_click_voice then
        return
    end
    -- 重置特殊部位
    if self._btnList then
        for k,v in pairs(self._btnList) do
            bee.removeAllClick(self._btnList[k])
        end
    end
    self._isSpecialInteract = false

    self._btnList = {}
    for i = 1, #cfg.special_click_voice, 2 do
        local name = cfg.special_click_voice[i]
        self._btnList[name] = self:find(name, self._roleSpine)
        if self._btnList[name] then
            bee.removeAllClick(self._btnList[name])
            bee.addClick2(self._btnList[name], function()
                if self._isSpecialInteract then
                    -- 交互动作过程中不允许交互
                    return
                end
                if self:isPlayingScrap() then
                    return
                end
                if not bee.checkCd("charater_interactive", 1) then
                    return
                end
                self._isSpecialInteract = true
                self:hideBubble()
                self:playAnim(name, self._skin, nil, function()
                    -- self:playAnim("idle", self._skin, "standby")
                    self:switchIdle()
                    self._isSpecialInteract = false
                end, false, true)
                Game:playRoleOutVoice(self._skinData.role, cfg.special_click_voice[i + 1])
                if callback then
                    callback()
                end
                bee.logEvent("lobby-character-click", CharacterModel:getUsingRoleId(), 2, name)
            end)
        end
    end
    return self._btnList
end

-- 可点击部位提示
function P:beginSpecialInteractionTips()
    if not self.EffTip then
        return
    end
    if not self._btnList or not next(self._btnList) then
        return
    end
    if not self._skinData.special_click_voice then
        return
    end

    if self._firstTipTag then
        scheduler:removeTag(self._firstTipTag)
        self._firstTipTag = nil
    end
    if self._tipsTag then
        scheduler:removeTag(self._tipsTag)
        self._tipsTag = nil
    end
    if self._stopTipTag then
        scheduler:removeTag(self._stopTipTag)
        self._stopTipTag = nil
    end

    if not self._skinEffList then
        self._skinEffList = {}
        for i = 1, #self._skinData.special_click_voice, 2 do
            table.insert(self._skinEffList, self._skinData.special_click_voice[i])
        end
    end

    self._effTipsMaxIndex = #self._skinEffList
    if not self._effTipsIndex then
        self._effTipsIndex = 1
    end

    self._firstTipTag = self:once(1, function()
        self._effShow = true

        local posObj1 = self._btnList[self._skinEffList[self._effTipsIndex]]
        if posObj1 then
            self.EffTip:SetActive(self._effShowFlag)
            self.EffTip.transform.position = posObj1.transform.position
        else
            self.EffTip:SetActive(false)
        end

        self._tipsTag = self:schedule(5, function()
            self._effTipsIndex = self._effTipsIndex + 1
            if self._effTipsIndex > self._effTipsMaxIndex then
                self._effTipsIndex = 1
            end

            local posObj = self._btnList[self._skinEffList[self._effTipsIndex]]
            if posObj then
                self.EffTip.transform.position = posObj.transform.position
                self.EffTip:SetActive(self._effShowFlag)
            else
                self.EffTip:SetActive(false)
            end
        end)
    end)
end

-- 停止可点击部位提示
function P:stopSpecialInteractionTips()
    if self._firstTipTag then
        scheduler:removeTag(self._firstTipTag)
        self._firstTipTag = nil
    end
    if self._tipsTag then
        scheduler:removeTag(self._tipsTag)
        self._tipsTag = nil
    end
    if self._stopTipTag then
        scheduler:removeTag(self._stopTipTag)
        self._stopTipTag = nil
    end
    self:setEffTipShow(false)
end

function P:setEffTipShow(flag)
    if not self.EffTip then
        return
    end
    self._effShowFlag = flag
    if not flag then
        self.EffTip:SetActive(false)
    else
        self.EffTip:SetActive(self._effShow)
    end
end

-- 初始化部件
function P:initAccessoriesInteraction(callback)
    local cfg = self._skinData
    if not cfg.accessories then
        return
    end
    self._accessoriesList = {}
    for _, name in pairs(cfg.accessories) do
        self._accessoriesList[name] = {}
        self._accessoriesList[name].obj = self:find(name, self._roleSpine)
        bee.removeAllClick(self._accessoriesList[name].obj)
        bee.addClick2(self._accessoriesList[name].obj, function()
            if self._isSpecialInteract then
                -- 交互动作过程中不允许交互
                return
            end
            if self:isPlayingScrap() then
                return
            end
            -- if not bee.checkCd("charater_interactive", 1) then
            --     return
            -- end
            if self._roleSpine then
                local cls = ObjectPool:getCls(self._roleSpine)
                if cls then
                    self._accessoriesList[name].flag = not self._accessoriesList[name].flag
                    cls:setAttachment(name, self._accessoriesList[name].flag)
                end
            end
        end)
    end
end

function P:resetAccessoriesFlag()
    if not self._accessoriesList then
        return
    end
    for k, v in pairs(self._accessoriesList) do
        v.flag = false
    end
end

function P:getSpineClickBtn()
    local SpineClick = self:find("SpineClick", self._roleSpine)
    if SpineClick then
        self.RoleSpine:GetComponent("Image").enabled = false
        self.RoleSpine:GetComponent("Button").enabled = false
        return SpineClick
    else
        self.RoleSpine:GetComponent("Image").enabled = true
        self.RoleSpine:GetComponent("Button").enabled = true
        return self.RoleSpine
    end
end

function P:initSpineClick(callback)
    if not callback then
        return
    end
    
    local clickBtn = self:getSpineClickBtn()
    bee.removeAllClick(clickBtn)
    bee.addClick2(clickBtn, function()
        callback()
    end)
end

function P:removeSpineClick()
    bee.removeAllClick(clickBtn)
    bee.addClick2(clickBtn, function()
        callback()
    end)
end

-- 初始化大厅交互语音
function P:initLobbyClickVoice(callback)
    local clickBtn = self:getSpineClickBtn()
    bee.removeAllClick(clickBtn)
    bee.addClick2(clickBtn, function()
        if self._isSpecialInteract then
            -- 交互动作过程中不允许交互
            return
        end
        if self:isPlayingScrap() then
            return
        end
        if self._isInLobbyVoice then
            self._isInLobbyVoice = nil
            self:hideBubble()
            -- self:playAnim(nil, self._skin, "standby")
            self:switchIdle()
            Game:stopRoleSound()
            return
        end
        if not bee.checkCd("charater_interactive", 1) then
            return
        end
        local chat = CharacterModel:getCharacterSound()
        if chat then
            self._isInLobbyVoice = true
            local length = Game:playRoleOutVoice(nil, chat.sound, true)
            self:showBubble(chat.text, length, function()
                self._isInLobbyVoice = nil
                if not bee.isNull(self.node) then
                    -- self:playAnim(nil, self._skin, "standby")
                    self:switchIdle()
                end
            end)
            self:playAnim(nil, self._skin, chat.face, nil, false)
            if callback then
                callback()
            end
        end
        bee.logEvent("lobby-character-click", CharacterModel:getUsingRoleId(), 1)
    end)
end

-- 初始化交互语音
function P:initClickVoice(chatList)
    self._chatList = chatList
    self._chatCount = #chatList
    self._chatIndex = 1
    bee.removeAllClick(self.RoleSpine)
    bee.addClick2(self.RoleSpine, function()
        if self:isPlayingScrap() then
            return
        end
        if not bee.checkCd("charater_interactive", 1) then
            return
        end
        local chat = self._chatList[self._chatIndex]
        if chat then
            local length = Game:playRoleOutVoice(nil, chat.sound, true)
            self:showBubble(chat.text, length)
            self:playAnim(nil, self._skin, chat.face, nil, false)
        end
        self._chatIndex = self._chatIndex + 1
        if self._chatIndex > self._chatCount then
            self._chatIndex = 1
        end
    end)
end

-- 播放单条语音
function P:playVoice(chat)
    local length = Game:playRoleOutVoice(nil, chat.sound, true)
    self._isInLobbyVoice = true
    self:showBubble(chat.text, length, function()
        self._isInLobbyVoice = nil
        if not bee.isNull(self.node) then
            self:playAnim(nil, self._skin, chat.face, nil, false)
        end
    end)
    self:playAnim(nil, self._skin, chat.face, nil, false)
end

-- 指定语音气泡框
function P:setBubbleItem(item)
    self._bubbleItem = item
    if not bee.isNull(self._bubbleItem) then
        self._bubbleItem:SetActive(false)
    end
end

-- 语音气泡
function P:showBubble(text, time, cb)
    if self._bubbleTag then
        scheduler:removeTag(self._bubbleTag)
        self._bubbleTag = nil
    end

    if self._bubbleItem then
        self._bubbleItem:SetActive(false)
    else
        self._bubbleItem = bee.createObj("views/BubbleItem")
        self._bubbleItem.transform:SetParent(self.node.transform)
        self._bubbleItem.transform.localPosition = bee.v3(0, -70, 0)
        self._bubbleItem.transform.localScale = bee.v3(1, 1, 1)
    end

    bee.setText(self:find("BubbleText", self._bubbleItem), _T(text))
    self._bubbleItem:SetActive(true)
    self._bubbleTag = self:once(time, function()
        self._bubbleItem:SetActive(false)
        if cb then
            cb()
        end
    end)
end

function P:hideBubble()
    if self._bubbleTag then
        scheduler:removeTag(self._bubbleTag)
        self._bubbleTag = nil
    end
    if self._bubbleItem then
        self._bubbleItem:SetActive(false)
    end
end

function P:stopVoice()
    Game:stopRoleSound()
    self:hideBubble()
end

-- 切换会默认动作
function P:switchIdle()
    if bee.isNull(self.node) then
        return
    end
    -- self:playAnim("idle", self._skin, "standby")
    if self._roleSpine then
        local cls = ObjectPool:getCls(self._roleSpine)
        if cls then
            cls:switchIdle()
        else
            self:playAnim("idle", self._skin, "standby")
        end
    end
    self._isSpecialInteract = false
end

function P:getShowSkinData(skin)
    return GF.getShowSkinData(skin, self._showReal)
    -- if not SettingModel:isShowSkin() and skin.kind ~= SKIN_KIND.NORMAL and not self._showReal then
    --     for _, v in ipairs(get_tpl_subKey(tpl_character_skin_list, "role", skin.role)) do
    --         if v.kind == SKIN_KIND.NORMAL then
    --             return v
    --         end
    --     end
    -- end
    -- return skin
end

function P:setRole(role, use_image_with_bg, allinAmin)
    self._btnList = nil
    self:hideBubble()
    self._role = role
    if self._role then
        local skin = self:getShowSkinData(role:getSkinData())
        self._skinData = skin
        local anim = skin and skin.movie
        if allinAmin then
            anim = skin and skin.table_allin
        end
        if anim then
            self.ImageRole:SetActive(false)
            if self._roleAnim ~= anim then
                self:removeRoleSpine()
                self._roleAnim = anim
                self._roleSpine = bee.createObj(anim)
                if self._roleSpine then
                    self._roleSpine.transform:SetParent(self.RoleSpine.transform, false)
                    self._roleSpine.transform.localPosition = bee.v3zero

                    local Image = self:find("Image", self._roleSpine)
                    if Image then
                        if use_image_with_bg then
                            Image:SetActive(true)
                        else
                            Image:SetActive(false)
                        end
                    end
                    local ImageFg = self:find("ImageFg", self._roleSpine)
                    if ImageFg then
                        if use_image_with_bg then
                            ImageFg:SetActive(true)
                        else
                            ImageFg:SetActive(false)
                        end
                    end
                end
            end
        else
            self._roleAnim = nil
            self:removeRoleSpine()
            self._roleSpine = nil
            self.ImageRole:SetActive(true)
            if use_image_with_bg and skin.image_with_bg then
                bee.setIcon(self.ImageRole, skin.image_with_bg, true)
                if skin.image_with_bg_offset then
                    self.ImageRole.transform.localPosition = bee.v3(skin.image_with_bg_offset[1], skin.image_with_bg_offset[2])
                    if skin.image_with_bg_offset[3] then
                        self.ImageRole.transform.localScale = bee.v3(skin.image_with_bg_offset[3], skin.image_with_bg_offset[3])
                    else
                        self.ImageRole.transform.localScale = bee.v3one
                    end
                else
                    self.ImageRole.transform.localPosition = bee.v3zero
                    self.ImageRole.transform.localScale = bee.v3one
                end
            else
                bee.setIcon(self.ImageRole, role:getSkinImage(), true)
                if skin.image_offset then
                    self.ImageRole.transform.localPosition = bee.v3(skin.image_offset[1], skin.image_offset[2])
                    if skin.image_offset[3] then
                        self.ImageRole.transform.localScale = bee.v3(skin.image_offset[3], skin.image_offset[3])
                    else
                        self.ImageRole.transform.localScale = bee.v3one
                    end
                else
                    self.ImageRole.transform.localPosition = bee.v3zero
                    self.ImageRole.transform.localScale = bee.v3one
                end
            end
        end
    end
end

function P:setSkin(skinData, use_image_with_bg, allinAmin)
    self:hideBubble()
    skinData = self:getShowSkinData(skinData)
    self._skinData = skinData
    local anim = skinData.movie
    if allinAmin then
        anim = skinData.table_allin
    end
    if anim then
        self.ImageRole:SetActive(false)
        if self._roleAnim ~= anim then
            self:removeRoleSpine()
            self:removeAllChildren(self.RoleSpine)
            self._roleAnim = anim
            self._roleSpine = bee.createObj(anim)
            if self._roleSpine then
                self._roleSpine.transform:SetParent(self.RoleSpine.transform, false)
                self._roleSpine.transform.localPosition = bee.v3zero

            end
        end
        if self._roleSpine then
            local Image = self:find("Image", self._roleSpine)
            if Image then
                if use_image_with_bg then
                    Image:SetActive(true)
                else
                    Image:SetActive(false)
                end
            end
            local ImageFg = self:find("ImageFg", self._roleSpine)
            if ImageFg then
                if use_image_with_bg then
                    ImageFg:SetActive(true)
                else
                    ImageFg:SetActive(false)
                end
            end
        end
    else
        self._roleAnim = nil
        self:removeRoleSpine()
        self._roleSpine = nil
        self.ImageRole:SetActive(true)
        self:removeAllChildren(self.RoleSpine)
        if use_image_with_bg and skinData.image_with_bg then
            bee.setIcon(self.ImageRole, skinData.image_with_bg, true)
            if skinData.image_with_bg_offset then
                self.ImageRole.transform.localPosition = bee.v3(skinData.image_with_bg_offset[1], skinData.image_with_bg_offset[2])
            else
                self.ImageRole.transform.localPosition = bee.v3zero
            end
        else
            bee.setIcon(self.ImageRole, skinData.image, true)
            if skinData.image_offset then
                self.ImageRole.transform.localPosition = bee.v3(skinData.image_offset[1], skinData.image_offset[2])
            else
                self.ImageRole.transform.localPosition = bee.v3zero
            end
            
            if skinData.image_offset and skinData.image_offset[3] then
                self.ImageRole.transform.localScale = bee.v3(skinData.image_offset[3], skinData.image_offset[3], skinData.image_offset[3])
            else
                self.ImageRole.transform.localScale = bee.v3one
            end
        end
    end
end

function P:setSkinImage(skinData, use_image_with_bg)
    skinData = self:getShowSkinData(skinData)
    self._skinData = skinData
    self:removeRoleSpine()
    if use_image_with_bg and skinData.image_with_bg then
        bee.setIcon(self.ImageRole, skinData.image_with_bg, true)
        if skinData.image_with_bg_offset then
            self.ImageRole.transform.localPosition = bee.v3(skinData.image_with_bg_offset[1], skinData.image_with_bg_offset[2])
        else
            self.ImageRole.transform.localPosition = bee.v3zero
        end
    else
        bee.setIcon(self.ImageRole, skinData.image, true)
        if skinData.image_offset then
            self.ImageRole.transform.localPosition = bee.v3(skinData.image_offset[1], skinData.image_offset[2])
        else
            self.ImageRole.transform.localPosition = bee.v3zero
        end
        if skinData.image_offset and skinData.image_offset[3] then
            self.ImageRole.transform.localScale = bee.v3(skinData.image_offset[3], skinData.image_offset[3], skinData.image_offset[3])
        else
            self.ImageRole.transform.localScale = bee.v3one
        end
    end
end

function P:setSkinRotate(flag)
    if not self._skinData then
        return
    end
    if false ~= flag then
        if self._skinData.spine_rotation then
            if self._roleSpine then
                self.RoleSpine.transform.localEulerAngles = bee.v3(0, 0, self._skinData.spine_rotation)
            else
                self.ImageRole.transform.localEulerAngles = bee.v3(0, 0, self._skinData.spine_rotation)
            end
        else
            self.RoleSpine.transform.localEulerAngles = bee.v3zero
            self.ImageRole.transform.localEulerAngles = bee.v3zero
        end
    else
        self.RoleSpine.transform.localEulerAngles = bee.v3zero
        self.ImageRole.transform.localEulerAngles = bee.v3zero
    end
end

function P:setImage(img)
    self:removeRoleSpine()
    bee.setIcon(self.ImageRole, img, true)
end

function P:setImageEnable(use_image_with_bg)
    if self._roleSpine then
        local Image = self:find("Image", self._roleSpine)
        if Image then
            Image:GetComponent("Image").enabled = use_image_with_bg
        end
    end
end

function P:removeRoleSpine()
    if self.EffTip then
        self.EffTip:SetActive(false)
        self._effTipsIndex = nil
        self._effShowFlag = true
    end

    if self._roleSpine then
        CU.GameObject.Destroy(self._roleSpine)
        self._roleSpine = nil
    end
end

function P:getRoleSpine()
    return self._roleSpine
end

function P:playAnim(anim, skin, face, onComplete, loop, clearFace)
    if self._roleSpine then
        local cls = ObjectPool:getCls(self._roleSpine)
        if cls then
            if clearFace then
                cls:clearFace()
            end
            cls:playAnim(anim, skin, face, onComplete, loop)
        else
            local node = self:find("Spine", self._roleSpine)
            if node then
                bee.spine(node):play(anim)
            end
        end
    end
end

function P:isPlayingScrap()
    if not self._roleSpine then
        return false
    end
    local cls = ObjectPool:getCls(self._roleSpine)
    if cls then
        return cls._isInScrap
    end
end

function P:playScrap()
    self:hideBubble()
    self:resetAccessoriesFlag()
    if self._roleSpine then
        if self._skinData then
            bee.invoke(self._roleSpine, "setSkinId", self._skinData.id)
        end
        bee.invoke(self._roleSpine, "playScrap")
    end
end

function P:stopScrap()
    self:hideBubble()
    self:resetAccessoriesFlag()
    if self._roleSpine then
        bee.invoke(self._roleSpine, "stopScrap")
    end
end

function P:setScrap(flag)
    if self._roleSpine then
        bee.invoke(self._roleSpine, "setScrap", flag)
    end
end

return P