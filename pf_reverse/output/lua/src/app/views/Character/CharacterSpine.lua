local P = class("CharacterSpine", Object)

-- 角色的 spine 动画
--[[
原皮default
爆衣scrap
爆衣动作scrap_switch
必杀技all_in

表情
待机standby
微笑smile
开心happy
害羞shy
无奈silence
难过sad
爆衣羞耻shame
]]
local FACES = {
    "standby", "smile", "happy", "shy", "silence", "sad", "shame"
}

function P:ctor(node, data)
end

function P:onAwake()
    self.Spine = self:find("Spine")
    self.Image = self:find("Image")
    self.ImageFg = self:find("ImageFg")
    if self.Image then
        self.Image:SetActive(false)
    end
    if self.ImageFg then
        self.ImageFg:SetActive(false)
    end
end

function P:onStart()
    self:playAnim("idle", self._skin or "skin1", "standby", nil, true)

    -- self:once(3, function()
    --     self:playScrap()
    -- end)
end

-- "None-无", "待机standby", "微笑smile", "开心happy", "害羞shy", "无奈silence", "难过sad", "爆衣羞耻shame"
function P:playFace(faceId)
    self._face = FACES[faceId] or "standby"
    self:playAnim(nil, self._skin, self._face)
end

function P:playAnimId(animId, count)
    local anims = {"idle", "scrap_switch"}
    local anim = anims[animId] or "idle"
    local skin = nil
    if anim == "scrap_switch" then
        skin = "skin2"
    end
    self:playAnim(anim, skin, nil, function()
        count = count - 1
        if count > 0 then
            self:playAnimId(animId, count)
        else
            self:playAnim("idle", nil, self._face or "standby")
        end
    end)
end

-- 添加气泡表情
function P:playSign(signId, pos)
    if not bee.isNull(self._sign) then
        CU.GameObject.Destroy(self._sign)
        self._sign = nil
    end
    local signs = {"Story[story_button_chat]"}
    self._sign = bee.createObj("views/Story/StorySign")
    if self._sign then
        bee.setIcon(self._sign, signs[signId] or signsp[1])
        self._sign.transform:SetParent(self.node.transform, false)
        self._sign.transform.localPosition = bee.v3(pos.x, pos.y)
        CU.GameObject.Destroy(self._sign, 3)
    end
end

function P:isInScrapState()
    if self._isInScrap then
        return true
    end
    if self._skin == "skin2" then
        return true
    end
    return false
end

function P:setScrap(flag)
    if flag then
        self._skin = "skin2"
        local sp = bee.spine(self.Spine)
        if sp:getSkin(self._skin) then
            sp:setSkin(self._skin)
        end
        if self._face then
            sp:attachSkin(self._face)
        end
    else
        self._skin = "skin1"
        local sp = bee.spine(self.Spine)
        if sp:getSkin(self._skin) then
            sp:setSkin(self._skin)
        end
        if self._face then
            sp:attachSkin(self._face)
        end
    end
end

function P:playScrap()
    self._isInScrap = true
    self:playAnim("scrap_switch", "skin2", nil, function()
        self:playAnim("idle", nil, self._face or "standby", nil, true)
        self:once(0.5, function()
            self:playAnim(nil, nil, self._face or "standby")
        end)
        self._isInScrap = nil

        if self._isWaitPause then
            self:once(0.1, function()
                if self._isWaitPause then
                    self:pauseAnim()
                end
            end)
        end
    end, false)
end

function P:tryPlayIdle()
    if self._anim ~= "idle" then
        self._isInScrap = nil
        self:playAnim("idle", self._skin, self._face or "standby", nil, true)
    end
end

function P:stopScrap()
    if self._isInScrap then
        self:playAnim("idle", "skin1", self._face or "standby")
        self._isInScrap = nil
    else
        self:playAnim(nil, "skin1", self._face or "standby")
    end
end

function P:pauseAnim(isWaitScrap)
    if isWaitScrap and self._isInScrap then
        self._isWaitPause = true
    else
        if not bee.isNull(self.Spine) then
            local sp = bee.spine(self.Spine)
            sp:pauseAnim()
        end
    end
end

function P:resumeAnim()
    self._isWaitPause = false
    if not bee.isNull(self.Spine) then
        local sp = bee.spine(self.Spine)
        sp:resumeAnim()
    end
end

-- 播放角色动作
function P:playAnim(anim, skin, face, onComplete, loop)
    if not bee.isNull(self.Spine) then
        local sp = bee.spine(self.Spine)
        if skin and sp:getSkin(skin) then
            sp:setSkin(skin)
            self._skin = skin
        end
        if face and sp:getSkin(face) then
            if self._face and self._face ~= face then
                sp:removeAttachSkin(self._face)
            end
            sp:attachSkin(face)
            self._face = face
        end
        if nil == loop then
            loop = true
        end
        if anim then
            sp:clearEvent()
            if onComplete then
                sp:onComplete(onComplete)
            end
            if sp:isHaveAnim(anim) then
                sp:play(anim, loop)
                self._anim = anim
            else
                local anims = sp.anim.Data.SkeletonData.Animations
                if anims.Count > 0 then
                    sp:play(anims.Items[0].Name, loop)
                    self._anim = anims.Items[0].Name
                end
            end
        end
        if self._hide_attachments then
            for _, v in ipairs(self._hide_attachments) do
                sp:removeAttachment(v)
            end
        end
    end
end

function P:clearFace()
    if self._face then
        local sp = bee.spine(self.Spine)
        sp:removeAttachSkin(self._face)
        self._face = nil
    end
end

function P:setAttachment(att, flag)
    local sp = bee.spine(self.Spine)
    if flag then
        sp:attachSkin(att)
    else
        sp:removeAttachSkin(att)
    end
end

-- 设置角色要隐藏的部件
function P:setHideAttachments(role_id)
    local d = tpl_character_spine_setting[role_id]
    if d then
        self._hide_attachments = d.hide_attachments
        if self._hide_attachments then
            local sp = bee.spine(self.Spine)
            for _, v in ipairs(self._hide_attachments) do
                sp:removeAttachment(v)
            end
        end
    end
end

function P:evt_onApplicationPause(paused)
    if not paused and self._skin then
        if not bee.isNull(self.Spine) then
            local sp = bee.spine(self.Spine)
            if sp:getSkin(self._skin) then
                sp:setSkin(self._skin)
                sp:attachSkin(self._face)
            end
            if self._hide_attachments then
                for _, v in ipairs(self._hide_attachments) do
                    sp:removeAttachment(v)
                end
            end
        end
    end
end

