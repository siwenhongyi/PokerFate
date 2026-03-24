---@class StoryModel
local P = class("StoryModel", BaseModel)

-- 剧情管理模块
function P:ctor()
	self.saveData = {
    }
	
	P.super.ctor(self)

    self._roles = {}
    self._curData = nil
    self._curIndex = 1
end

function P:afterInit()
end

function P:updateStoryRed()
end

function P:getStoryData()
    return self._curData
end

function P:setStoryData(data)
    self._curData = data
    self._curIndex = 1
end

function P:getCurIndex()
    return self._curIndex
end

function P:setCurIndex(index)
    self._curIndex = index
end

function P:getTalkName(data)
    local name = data.name or ""
    if not name or "" == name and data.role then
        local d = tpl_story_characters[data.role]
        if d then
            name = d.name or ""
        end
    end
    return _T(name)
end

-- 完成剧情
function P:doneStory()
end

function P:skipStory()
    self.isSkip = true
    UiManager:hideUI("Story")
    if GuideManager:isInGuide() then
        GuideManager:doGuideEnd()
    end
end

function P:isInCurNode(nodeId)
    for _, v in ipairs(self.cloud.curNodes) do
        if v == nodeId then
            return true
        end
    end
    return false
end

function P:getNones()
    return self.cloud.dones
end

function P:getNonesCount()
    if not self.cloud.dones then
        return 0
    end
    return #self.cloud.dones
end

function P:addRole(role)
    for k, v in ipairs(self.cloud.roles) do
        if v.role == role.role then
            self.cloud.roles[k] = role
            self._roles[role.role] = role
            self:onSave()
            return
        end
    end
    table.insert(self.cloud.roles, role)
    self._roles[role.role] = role
    self:onSave()
end

function P:removeRole(role)
    for k, v in ipairs(self.cloud.roles) do
        if v.role == role.role then
            table.remove(self.cloud.roles, k)
            self._roles[role.role] = nil
            self:onSave()
        end
    end
end

function P:getRole(id)
    return self._roles[id]
end

function P:getRoles(id)
    return self._roles
end

function P:isInDone(nodeId)
    for _, v in ipairs(self.cloud.dones) do
        if v == nodeId then
            return true
        end
    end
end

function P:getStageDatas(id)
    return get_tpl_subKey(tpl_storyStage_list, "episode", id or self:getCurId())
end

-- 0 章节未解锁  1 当前章节已解锁未开始  2 当前章节已开始
function P:getLock()
    return self.cloud.lock or 0
end

function P:setLock(int)
    if self.cloud.lock ~= int then
        self.cloud.lock = int
        self:onSave()
    end
end

-- 获取触发点所能创建的角色列表，包含在它之前的触发点所创建及移动的
function P:getStageRoles(stageId)
    local roles = {}
    -- local d = tpl_storyStage[stageId]
    -- if d then
    --     local tbs = self:getStageDatas(d.episode)
    --     for _, v in ipairs(tbs) do
    --         if v.id >= stageId then
    --             break
    --         end

    --         local data = self:loadStageData(v.id)
    --         if data then
    --             self:_cloneRolesData(data, roles)
    --         end
    --     end
    -- end
    return roles
end

function P:_cloneRolesData(stageData, roles, isAddToCloud)
    if stageData then
        if stageData.objs then
            for _, r in ipairs(stageData.objs) do
                if Config.STAGE_NODE_ROLE_NEW == r.kind then
                    if isAddToCloud then
                        if not self:getRole(r.role) then
                            self:addRole(clone(r))
                        end
                    else
                        roles[r.role] = clone(r)
                    end
                end
            end
        end
        if stageData.nodes then
            for _, n in ipairs(stageData.nodes) do
                if Config.STAGE_NODE_TRANS_SCENE == n.kind then
                    if isAddToCloud then
                        self.cloud.scene = n.ival
                    end
                elseif Config.STAGE_NODE_CAMERA == n.kind then
                    if isAddToCloud then
                        self.cloud.scenePosition = n.position
                    end
                elseif Config.STAGE_NODE_ROLE_NEW == n.kind then
                    if isAddToCloud then
                        if not self:getRole(n.role) then
                            self:addRole(clone(n))
                        end
                    else
                        roles[n.role] = clone(n)
                    end
                elseif Config.STAGE_NODE_ROLE_ANIM == n.kind then
                    local role = roles[n.role]
                    if role then
                        role.sign = n.sign
                        role.emote = n.emote
                        role.anim = n.anim
                        role.skin = n.skin
                        role.position2 = n.position2
                    end
                elseif Config.STAGE_NODE_ROLE_MOVE == n.kind then
                    local role = roles[n.role]
                    if role then
                        role.position = n.position
                        role.position2 = n.position2
                        role.sign = n.sign
                        role.emote = n.emote
                        role.anim = n.anim
                        role.skin = n.skin
                    end
                elseif Config.STAGE_NODE_ROLE_TOWARD == n.kind then
                    local role = roles[n.role]
                    if role then
                        role.toward = n.toward
                    end
                elseif Config.STAGE_NODE_ROLE_DEL == n.kind then
                    if isAddToCloud then
                        if self:getRole(n.role) then
                            self:removeRole(clone(n))
                        end
                    else
                        roles[n.role] = nil
                    end
                elseif Config.STAGE_NODE_ROLE_SCALE == n.kind then
                    local role = roles[n.role]
                    if role then
                        role.val = n.val
                    end
                end
            end
        end
    end
end

function P:loadStageData(id)
    local f = ResManager:GetTextAsset("storys/story_" .. id .. ".json")
    local s = f and f.bytes or ""

    if s and "" ~= s then
        return json.decode(s)
    end
    return nil
end

function P:loadStageDataByName(name)
    local f = ResManager:GetTextAsset("storys/" .. name .. ".json")
    local s = f and f.bytes or ""

    if s and "" ~= s then
        return json.decode(s)
    end
    return nil
end

-- 创建角色模型
function P:createRole(roleId, data)
    local d = tpl_story_characters[roleId]
    if d then
        if d.spine_res then
            local obj = bee.createObj(d.spine_res)
            if obj then
                return require("app.Story.StoryRole"):create(roleId, obj, data)
            end
        elseif d.avatar then
            local obj = bee.createObj("views/Story/StoryImage")
            if obj then
                bee.setIcon(obj, d.avatar, true)
                return require("app.Story.StoryRole"):create(roleId, obj, data)
            end
        end
    end
    return nil
end

function P:createThing(iconId)
    local obj = bee.createObj("New_effect/SpineRole/Thing")
    if obj then
        return require("app.Story.StoryThing"):create(iconId, obj)
    end
    return nil
end

-- 播放玩家动作
function P:playRoleAnim(spineNode, data)
    if not bee.isNull(spineNode) then
        local sp = bee.spine(spineNode)
        if not sp then
            return
        end
        if sp:getSkin(data.skin) then
            sp:setSkin(data.skin)
        end
        if data.emote and "" ~= data.emote and string.find(data.emote, "head_") then
            sp:attachSkin(data.emote)
        end
        if sp:isHaveAnim(data.anim) then
            sp:play(data.anim, true)
        else
            local anims = sp.anim.Data.SkeletonData.Animations
            if anims.Count > 0 then
                sp:play(anims.Items[0].Name, true)
            end
        end
    end
end

function P:getCurNodeRoleCfg()
    local nodeId = self.cloud.curNodes[#self.cloud.curNodes]
    if nodeId then
        return tpl_storyStage[nodeId].role
    end
end

function P:setFirstStage(bool)
    self.firstStage = bool
end

function P:getFirstStage(bool)
    return self.firstStage
end

return P


