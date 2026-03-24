local StoryNode = require("app.Story.StoryNode")
local P = class("Story", UiBase)

function P:onAwake()
	self._openAnim, self._closeAnim = "UI_1_" .. self.__cname .. "_into", "UI_1_" .. self.__cname .. "_back"
    self.AnimRoot = self:find("AnimRoot")
    self.Scene = self:find("Scene", self.AnimRoot)
    self.Center = self:find("Center", self.AnimRoot)
    self.Bottom = self:find("Bottom", self.AnimRoot)
    self.RightTop = self:find("RightTop", self.AnimRoot)

    self.TextCG = self:find("TextCG", self.Bottom)
    self.Dialog = self:find("Dialog", self.Bottom)
    self.TextName = self:find("TextName", self.Dialog)
    self.TextContent = self:find("TextContent", self.Dialog)

    self.ImageScene = self:find("ImageScene", self.Scene)
    self.ImageClick = self:find("ImageClick", self.AnimRoot)
    self.ImageSceneTrans = self:find("ImageSceneTrans", self.AnimRoot)
    self.BgOptions = self:find("BgOptions", self.AnimRoot)
    self.DialogItem1 = self:find("DialogItem1", self.Center)
    self.DialogItem1:SetActive(false)

    self.SkipButton = self:find("SkipButton", self.RightTop)
    self.SkipTalkButton = self:find("SkipTalkButton", self.RightTop)
    self.SkipTalkButton2 = self:find("SkipTalkButton2", self.RightTop)
    self.HideButton = self:find("HideButton", self.RightTop)
    self.ChatButton = self:find("ChatButton", self.RightTop)
    self.Auto = self:find("Auto", self.RightTop)
    self.PlayButton = self:find("PlayButton", self.Auto)
    self.AutoPlayButton = self:find("AutoPlayButton", self.Auto)

    bee.addClick(self.SkipButton, function()
        local params = {}
        if self._params then
            params.hotSpringdata = self._params.hotSpringdata
        end
        params.curData = self._curNode and self._curNode._data or {}
        UiManager:showUI(self._params and self._params.StorySkip or "StorySkip", params)
    end)
    bee.addClick(self.SkipTalkButton, function()
        self:onBtNextTalk()
    end)
    bee.addClick(self.SkipTalkButton2, function()
        self:onBtNextTalk()
    end)
    bee.addClick(self.HideButton, function()
        self:showButtons(false, true)
        self._isHideUI = true
    end)
    bee.addClick(self.ChatButton, function()
        UiManager:showUI(self._params and self._params.StoryRecord or "StoryRecord")
    end)
    bee.addClick(self.PlayButton, function()
        self._isAutoPlay = true
        self.PlayButton:SetActive(not self._isAutoPlay)
        self.AutoPlayButton:SetActive(self._isAutoPlay)
    end)
    bee.addClick(self.AutoPlayButton, function()
        self._isAutoPlay = false
        self.PlayButton:SetActive(not self._isAutoPlay)
        self.AutoPlayButton:SetActive(self._isAutoPlay)
    end)
    bee.addClick2(self.ImageClick, function()
        if self._isHideUI then
            self:showButtons(true, true)
            self._isHideUI = nil
        end
        if not bee.checkCd("story_next_click", 0.2) then
            return
        end
        self:onBtNextClick()
    end)

    self._inEdit = nil      -- 是否在编辑模式
    self._curData = nil     -- 当前剧情点的数据，用于编辑器
    self._roles = {}
    self._rolesPos = {}
    self._isAutoPlay = false
    self._curNodeIndex = 0
    self._isOnlySkip2 = false
end

function P:onStart()
    self.TextCG:SetActive(false)
    self.Dialog:SetActive(false)
    -- self.TextName:SetActive(false)
    -- self.TextContent:SetActive(false)
    self.PlayButton:SetActive(not self._isAutoPlay)
    self.AutoPlayButton:SetActive(self._isAutoPlay)

    if self._inEdit then
        self.RightTop:SetActive(false)
        self.ImageClick:SetActive(false)
    end

    if self._params then
        local data
        if self._params.id then
            data = StoryModel:loadStageData(self._params.id)
        elseif self._params.name then
            data = StoryModel:loadStageDataByName(self._params.name)
        end
        if data then
            self:evt_clearStory()
            self._curNodeIndex = 0
            self._viewIndex = self._params.index or 0
            self:evt_loadStory(data)
            self:evt_loadStoryScene(self._curData.sceneId, true)
            self:startPlay()
        end
    end
    StoryModel.isSkip = nil
end

function P:onHide()
    P.super.onHide(self)
    Game:playLobbyBGM()
end

function P:isAutoPlay()
    return self._isAutoPlay
end

function P:showButtons(isVisible, isFade)
    if isFade then
        if self._isOnlySkip2 then
            self.SkipButton:SetActive(false)
            self.SkipTalkButton:SetActive(false)
            self.SkipTalkButton2:SetActive(true)
            self.HideButton:SetActive(false)
            self.ChatButton:SetActive(false)
            self.Auto:SetActive(false)
        else
            self.SkipButton:SetActive(true)
            self.SkipTalkButton:SetActive(true)
            self.SkipTalkButton2:SetActive(false)
            self.HideButton:SetActive(true)
            self.ChatButton:SetActive(true)
            self.Auto:SetActive(true)
        end
        if isVisible then
            bee.playAnimator(self.RightTop, "UI_1_Story_Button_into")
        else
            bee.playAnimator(self.RightTop, "UI_1_Story_Button_back")
        end
    else
        if self._isOnlySkip2 then
            self.SkipButton:SetActive(false)
            self.SkipTalkButton:SetActive(false)
            self.SkipTalkButton2:SetActive(isVisible)
            self.HideButton:SetActive(false)
            self.ChatButton:SetActive(false)
            self.Auto:SetActive(false)
        else
            self.SkipButton:SetActive(isVisible)
            self.SkipTalkButton:SetActive(isVisible)
            self.SkipTalkButton2:SetActive(false)
            self.HideButton:SetActive(isVisible)
            self.ChatButton:SetActive(isVisible)
            self.Auto:SetActive(isVisible)
        end
    end
end

function P:onBtNextClick()
    if self._curNode then
        if self._curNode:onClick() then
            return
        end
        if self._curNode:isOver() then
            self:playNextNode()
        end
    end
end

function P:onBtNextTalk()
    if not self._curNode then
        return
    end
    if self._params and self._params.hotSpringdata then
        bee.logEvent("onse-plot_skip_single", self._params.hotSpringdata.id, self._params.hotSpringdata.group, self._curNode._data._index or 1)
    elseif self._params and self._params.StoryRecord == "GalaSeasonLog" then
        bee.logEvent("galaseason-plot_skip_single", StoryModel.storyData.id, StoryModel.storyData.group, self._curNode._data._index or 1)
    end
    if GuideManager:isInGuide() then
        bee.logEvent("guide-id-skip", GuideManager.curGuide.id, self._curNode._data._index or 1)
    end
    if self._curNode and self._curNode._data.kind == 2001 then
        self:playNextNode(nil, true)
    end
end

function P:startPlay()
    local isSkip = self._viewIndex > self._curNodeIndex + 1
    if not isSkip and self._curData.fadeInDt and self._curData.fadeInDt > 0 then
        self:showButtons(false)
        self._curNode = StoryNode:create({
            kind = 9001, dt = self._curData.fadeInDt, triType = 0,
            cb = function()
                self:showButtons(true)
            end
        })
        self._curNode:onEvent(self)
    else
        self:playNextNode()
    end
end

function P:playNextNode(isSkip, isFast)
    if self._viewIndex and not isSkip then
        isSkip = self._viewIndex > self._curNodeIndex + 1
    end
    if self._curData and self._curData.nodes then
        self._curNodeIndex = self._curNodeIndex + 1
        StoryModel:setCurIndex(self._curNodeIndex)
        local node = self._curData.nodes[self._curNodeIndex]
        if node then
            if self._curNode then self._curNode:onExit() end
            self._curNode = StoryNode:create(node)
            self._curNode:onEvent(self, isSkip, isFast)
        else
            self._curNode = nil

            if self._curData.fadeInDt and self._curData.fadeInDt > 0 then
                self.ImageSceneTrans:SetActive(true)
                local cmp = self.ImageSceneTrans:GetComponent("Image")
                cmp.color = CU.Color(0, 0, 0, 0)
                bee.tween(self.ImageSceneTrans)
                : to(self._curData.fadeInDt, {opacity = 1})
                : ease(DT.Ease.Linear)
                : onComplete(function()
                    if GuideManager:isInGuide() then
                        self.ImageSceneTrans:SetActive(false)
                    end
                    self:onStoryOver()
                end)
                : link()
            else
                self:onStoryOver()
            end
        end
    end
end

function P:isStoryOver()
    if self._curData and self._curData.nodes then
        return self._curData.nodes[self._curNodeIndex + 1] == nil
    end
    return true
end

function P:onStoryOver()
    bee.emit("evt_stageEnd")
    if not self._inEdit then
        self:hideUI()
        GuideManager:doGuideEnd()
    end
end

function P:switchScene(data, isSkip)
    if data.sceneId then
        local d = tpl_story_scenes[data.sceneId]
        local obj = nil
        if d and d.prefab then
            obj = bee.createObj(d.prefab)
        elseif d and d.image then
            obj = CU.GameObject.Instantiate(self.ImageScene)
            bee.setIcon(obj, d.image, true)
        end
        if obj then
            obj.transform:SetParent(self.Scene.transform, false)
            obj.transform.localPosition = bee.v3(data.position.x, data.position.y)
            obj.transform.localScale = bee.v3(data.scale, data.scale, data.scale)
        end
        local uiFunc = function() end
        if data.hideUi and not isSkip then
            if self.RightTop.activeSelf then
                self.RightTop:SetActive(false)
                uiFunc = function()
                    self.RightTop:SetActive(true)
                end
            end
        end
        local dt = data.dt or 1
        -- 【默认】、【黑幕转场】、【白幕转场】、【渐变转场】、【横向擦除转场】
        if 0 == data.trans or isSkip then
        elseif 1 == data.trans then
            self.ImageSceneTrans:SetActive(true)
            obj:SetActive(false)
            local cmp = self.ImageSceneTrans:GetComponent("Image")
            cmp.color = CU.Color(0, 0, 0, 0)
            bee.tween(self.ImageSceneTrans)
            : to(dt/2, {opacity = 1})
            : call(function()
                obj:SetActive(true)
                bee.tween(self.ImageSceneTrans)
                : to(dt/2, {opacity = 0})
                : onComplete(function()
                    uiFunc()
                end)
                : ease(DT.Ease.Linear)
                : link()
            end)
            : ease(DT.Ease.Linear)
            : link()
        elseif 2 == data.trans then
            self.ImageSceneTrans:SetActive(true)
            obj:SetActive(false)
            local cmp = self.ImageSceneTrans:GetComponent("Image")
            cmp.color = CU.Color(1, 1, 1, 0)
            bee.tween(self.ImageSceneTrans)
            : to(dt/2, {opacity = 1})
            : call(function()
                obj:SetActive(true)
                bee.tween(self.ImageSceneTrans)
                : to(dt/2, {opacity = 0})
                : onComplete(function()
                    uiFunc()
                end)
                : ease(DT.Ease.Linear)
                : link()
            end)
            : ease(DT.Ease.Linear)
            : link()
        elseif 3 == data.trans then
            self.ImageScene:SetActive(false)
            bee.tween(self._curScene)
            : to(dt, {alphaBetween = {1, 0}})
            : ease(DT.Ease.Linear)
            : link()
            bee.tween(obj)
            : to(dt, {alphaBetween = {0, 1}})
            : ease(DT.Ease.Linear)
            : onComplete(function()
                self.ImageScene:SetActive(true)
                uiFunc()
            end)
            : link()
        elseif 4 == data.trans then
            self.ImageScene:SetActive(false)
            bee.tween(self._curScene)
            : to(dt, {position = bee.v3(SCREEN_WIDTH / 2, 0)})
            : ease(DT.Ease.Linear)
            : link()
            obj.transform.localPosition = bee.v3(-SCREEN_WIDTH / 2, 0)
            bee.tween(obj)
            : to(dt, {position = bee.v3(data.position.x, data.position.y)})
            : ease(DT.Ease.Linear)
            : onComplete(function()
                self.ImageScene:SetActive(true)
                uiFunc()
            end)
            : link()
        end
        if data.leave then
            self:clearRoles()
        end
        self._curScene = obj
    end
end

function P:showDialog(visible, fade)
    if visible then
        if not self.Dialog.activeSelf then
            self.Dialog:SetActive(true)
            if fade then
                bee.setAlpha(self.Dialog, 0)
                bee.tween(self.Dialog)
                : to(0.2, {alphaBetween = {0, 1}})
                : link()
            end
        end
    else
        if self.Dialog.activeSelf then
            if fade then
                bee.tween(self.Dialog)
                : to(0.1, {alphaBetween = {1, 0}})
                : onComplete(function()
                    self.Dialog:SetActive(false)
                end)
                : link()
            else
                self.Dialog:SetActive(false)
            end
        end
    end
end

function P:showTalk(data, text, isAll)
    if 0 == data.style then
        self:showDialog(true, data.fadeIn)
        self.TextCG:SetActive(false)
        local name = StoryModel:getTalkName(data)
        bee.setText(self.TextName, name)
        self:find("story_dialog_line", self.Dialog):SetActive(name ~= "")
        if text then
            bee.setText(self.TextContent, text)
        else
            bee.setText(self.TextContent, _F(data.text), _T(data.name))
        end
        self:find("story_dialog_arrow", self.Dialog):SetActive(data.showType ~= 1 or isAll)
    else
        self:showDialog(false, data.fadeOut)
        self.TextCG:SetActive(true)
        if text then
            bee.setText(self.TextCG, text)
        else
            bee.setText(self.TextCG, _F(data.text), _T(data.name))
        end
    end
    -- 置灰效果 0除发言人外置灰 1所有人置灰 2所有人不置灰
    if 0 == data.gray then
        self:setRolesGray(true, data.role)
    elseif 1 == data.gray then
        self:setRolesGray(true)
    else
        self:setRolesGray(false)
    end
end

function P:setRoleGray(data)
    local role = self._roles[data.role]
    if role then
        if data.gray then
            self:setRoleColor(role.node, CU.Color(0.4, 0.4, 0.4, 1))
        else
            self:setRoleColor(role.node, CU.Color(1, 1, 1, 1))
        end
    end
end

function P:setRolesGray(isGray, roleId)
    for _, role in pairs(self._roles) do
        if isGray and role.roleId ~= roleId then
            self:setRoleColor(role.node, CU.Color(0.4, 0.4, 0.4, 1))
        else
            self:setRoleColor(role.node, CU.Color(1, 1, 1, 1))
        end
    end
end

function P:setRoleColor(node, color)
    local sp = self:find("Spine", node)
    if sp then
        sp:GetComponent("SkeletonGraphic").color = color
    else
        local img = node:GetComponent("Image")
        if img then
            img.color = color
        end
    end
end

function P:setRoleFade(node, opacity, fadeDt, cb)
    local sp = self:find("Spine", node)
    if sp then
        bee.tween(sp)
        : to(fadeDt, {opacity = opacity}, {opacity = "SkeletonGraphic"})
        : onComplete(cb or function() end)
        : link()
    else
        bee.tween(node)
        : to(fadeDt, {opacity = opacity})
        : onComplete(cb or function() end)
        : link()
    end
end

function P:createRole(data, inEditor, isSkip)
    local role = self._roles[data.role]
    if not inEditor and role then
        role.node:SetActive(true)
    else
        role = StoryModel:createRole(data.role, data)
        role.node.transform:SetParent(self.Center.transform, false)
        if not inEditor then
            self._roles[role.roleId] = role
        end
    end
    
    role.node.transform.localPosition = bee.v3(data.position.x, data.position.y)
    role.node.transform.localScale = bee.v3(data.scale, data.scale, data.scale)
    self._rolesPos[data.role] = role.node.transform.localPosition
    self:adjustRoleLayer()

    -- self:playRoleAnim(data, role)
    -- self:scaleRole(data, true)
    -- self:towardRole(data)

    if not inEditor then
        if data.face > 0 then
            ObjectPool:getCls(role.node):playFace(data.face)
        end
        local color = CU.Color(1, 1, 1, 1)
        if data.gray then
            color.r, color.g, color.b = 0.4, 0.4, 0.4
        end
        if data.fadeInDt > 0 and not isSkip then
            color.a = 0
            self:setRoleColor(role.node, color)
            self:setRoleFade(role.node, 1, data.fadeInDt)
        else
            self:setRoleColor(role.node, color)
        end
        if data.move and not isSkip then
            role.node.transform.localPosition = bee.v3(data.startPos.x, data.startPos.y)
            bee.tween(role.node)
            : to(data.moveDt, {position = bee.v3(data.position.x, data.position.y)})
        end
    end

    return role
end

function P:removeRole(data, isSkip)
    local role = self._roles[data.role]
    if role then
        self._roles[data.role] = nil
        local color = CU.Color(1, 1, 1, 1)
        if data.gray then
            color.r, color.g, color.b = 0.4, 0.4, 0.4
        end
        self:setRoleColor(role.node, color)
        if data.fadeOutDt > 0 and not isSkip then
            self:setRoleFade(role.node, 0, data.fadeOutDt, function()
                CU.GameObject.Destroy(role.node)
            end)
        else
            CU.GameObject.Destroy(role.node)
        end
    end
end

function P:playRoleFace(data)
    local role = self._roles[data.role]
    if role and data.face and data.face > 0 then
        local cls = ObjectPool:getCls(role.node)
        if cls then cls:playFace(data.face) end
    end
end

function P:playSign(data)
    local role = self._roles[data.role]
    if role and data.sign > 0 then
        local cls = ObjectPool:getCls(role.node)
        if cls then cls:playSign(data.sign, data.position) end
    end
end

function P:playRoleAnim(data)
    local role = self._roles[data.role]
    if role and data.anim > 0 then
        local cls = ObjectPool:getCls(role.node)
        if cls then cls:playAnimId(data.anim, data.count) end
    end
end

function P:clearRoles()
    if next(self._roles) then
        for k, v in pairs(self._roles) do
            CU.GameObject.Destroy(v.node)
        end
        self._roles = {}
    end
end

function P:adjustRoleLayer()
    local roleList = {}
    for _, v in pairs(self._roles) do
        table.insert(roleList, v)
    end
    table.sort(roleList, function(a, b) 
        return a.data.zOrder < b.data.zOrder
    end)
    for _, v in ipairs(roleList) do
        v.node.transform:SetAsLastSibling()
    end
end

function P:playBGM(data)
    if data.audio and data.audio ~= "" then
        Game:stopMusic()
        bee.playMusic(data.audio, false, SettingModel:getLobbyBGMVolume())
        if not data.autoPlay then
            CS.SoundManager.Instance:PauseMusic()
        end
        self._isPlayBGM = true
    end
end

function P:pauseBGM(data)
    if self._bgmTween then
        self._bgmTween:Kill()
        self._bgmTween = nil
    end
    if data.fadeOut and data.dt > 0 and SettingModel:getLobbyBGMVolume() > 0 then
        self._bgmTween = bee.Tween.toFloat(SettingModel:getLobbyBGMVolume(), 0, data.dt, function(v)
            if bee.isNull(self.node) then
                return
            end
            bee.changeMusicVolume(v)
            if v <= 0 then
                CS.SoundManager.Instance:PauseMusic()
                self._bgmTween = nil
            end
        end)
    else
        CS.SoundManager.Instance:PauseMusic()
    end
end

function P:resumeBGM(data)
    if self._bgmTween then
        self._bgmTween:Kill()
        self._bgmTween = nil
    end
    CS.SoundManager.Instance:UnPauseMusic()
    if data.fadeIn and data.dt > 0 and SettingModel:getLobbyBGMVolume() > 0 then
        self._bgmTween = bee.Tween.toFloat(0, SettingModel:getLobbyBGMVolume(), data.dt, function(v)
            bee.changeMusicVolume(v)
            if v >= SettingModel:getLobbyBGMVolume() then
                self._bgmTween = nil
            end
        end)
    end
end

function P:playSound(data)
    Game:stopStoryVoice()
    if data.audio and data.audio ~= "" then
        self._soundIndex = Game:playStoryVoice(data.audio)
        local audio = ResManager:GetSound(data.audio)
        if audio then
            return audio.length
        end
    elseif data.voice and data.voice ~= "" then
        self._soundIndex = Game:playStoryVoice(data.voice)
        local audio = ResManager:GetSound(data.voice)
        if audio then
            return audio.length
        end
    end
    return 0
end

function P:clearSound(data)
    if data.fadeOut and data.dt > 0 then
        bee.Tween.toFloat(1, 0, data.dt, function(v)
            bee.changeSoundVolume(self._soundIndex, v)
            if v <= 0 then
                -- bee.stopSound("")
                Game:stopStoryVoice()
            end
        end)
    else
        -- bee.stopSound("")
        Game:stopStoryVoice()
    end
end

-- 0全部显示 1全部隐藏 2对话框显示 3对话框隐藏
function P:hideShowUI(data)
    if 0 == data.showType then
        self._isOnlySkip2 = false
        self.RightTop:SetActive(true)
        self.SkipTalkButton:SetActive(true)
        self.SkipTalkButton2:SetActive(false)
        if data.fade then
            bee.playAnimator(self.RightTop, "UI_1_Story_Button_into")
        else
            bee.playAnimator(self.RightTop, "UI_1_Story_Button_idle")
        end
        self:showDialog(true, data.fade)
        self.TextCG:SetActive(true)
    elseif 1 == data.showType then
        if data.fade then
            bee.playAnimator(self.RightTop, "UI_1_Story_Button_back")
        else
            self.RightTop:SetActive(false)
        end
        self:showDialog(false, data.fade)
        self.TextCG:SetActive(false)
    elseif 2 == data.showType then
        self:showDialog(true, data.fade)
        self.TextCG:SetActive(true)
    elseif 3 == data.showType then
        self:showDialog(false, data.fade)
        self.TextCG:SetActive(false)
    elseif 4 == data.showType then
        self._isOnlySkip2 = true
        self.RightTop:SetActive(true)
        self.SkipButton:SetActive(false)
        self.SkipTalkButton:SetActive(false)
        self.SkipTalkButton2:SetActive(true)
        self.HideButton:SetActive(false)
        self.ChatButton:SetActive(false)
        self.Auto:SetActive(false)
        if data.fade then
            bee.playAnimator(self.RightTop, "UI_1_Story_Button_into")
        else
            bee.playAnimator(self.RightTop, "UI_1_Story_Button_idle")
        end
        self:showDialog(false, data.fade)
        self.TextCG:SetActive(false)
    end
end

function P:showOptions(data)
    for k, v in ipairs(data.options) do
        local item = CU.GameObject.Instantiate(self.DialogItem1)
        item:SetActive(true)
        item.transform:SetParent(self.BgOptions.transform, false)
        bee.setText(self:find("Ani_root/Text", item), _T(v.option))
        bee.addClick(item, function()
            self:removeAllChildren(self.BgOptions)
            if not v.storyId or v.storyId <= 0 then
                self:playNextNode()
            elseif not self._inEdit then
                local data = StoryModel:loadStageData(v.storyId)
                if data then
                    self:evt_clearStory()
                    self:evt_loadStory(data)
                    self:evt_loadStoryScene(self._curData.sceneId)
                    self:startPlay()
                end
            end
        end)
        if k > 1 then
            self:find("Ani_root", item):SetActive(false)
            self:once((k - 1) * 0.1, function()
                self:find("Ani_root", item):SetActive(true)
            end)
        end
    end
end

function P:refreshStory()
    self:clearRoles()
    self.Dialog:SetActive(false)
    self.TextCG:SetActive(false)
    self:removeAllChildren(self.BgOptions)

    -- for _, v in ipairs(self._curData.nodes) do
    --     if v.kind == 2002 then
    --         self:createRole(v)
    --     end
    -- end

    -- if self._inEdit then
    --     self:switchRoleShow(false)
    -- end

    -- local roles = StoryModel:getRoles()
    -- if self._inEdit then
    --     roles = StoryModel:getStageRoles(self._curData.id)
    -- end

    -- for _, v in pairs(roles) do
    --     self:createRole(v)
    -- end
end


function P:evt_stageEnter(index)
    self._curNodeIndex = 0
    self._viewIndex = index or 0
    self.RightTop:SetActive(true)
    self.ImageClick:SetActive(true)
    self:evt_loadStoryScene(self._curData.sceneId, true)
    self:startPlay()
    
    -- self:switchRoleShow(true)
end

function P:evt_stageExit()
    self.ImageClick:SetActive(false)
    self:refreshStory()
    self:evt_loadStoryScene(self._curData.sceneId)
    self:switchRoleShow(false)
    if self._isPlayBGM then
        self._isPlayBGM = nil
        if bee.isInHome() then
            Game:playLobbyBGM()
        else
            Game:stopMusic()
        end
    end
end

--隐藏显示角色
function P:switchRoleShow(bool)
    for i, v in pairs(self._roles) do
        if v and v.node and not bee.isNull(v.node) then
            if bool then
                v.node.transform.localPosition = self._rolesPos[i] or bee.v3()
            else
                v.node.transform.localPosition = bee.v3(10000, 10000, 0)
            end
        end
    end
end

-- 加载一个剧情
function P:evt_loadStory(story, notRefresh)
    if not story then
        return
    end

    self._curData = story
    for k, v in ipairs(self._curData.nodes) do
        v._index = k
    end
    StoryModel:setStoryData(self._curData)
	
    if not notRefresh then
        self:refreshStory()
    end
end

-- 清除所有剧情
function P:evt_clearStory()
end

function P:evt_loadStoryScene(sceneId, trans)
    if sceneId and "" ~= sceneId then
        if self._curScene then
            CU.GameObject.Destroy(self._curScene)
            self._curScene = nil
        end
        local d = tpl_story_scenes[sceneId]
        if d and d.prefab then
            local obj = bee.createObj(d.prefab)
            if obj then
                self.ImageScene:SetActive(false)
                obj.transform:SetParent(self.Scene.transform, false)
                obj.transform.localPosition = bee.v3zero
                self._curScene = obj
            end
        end
        if not self._curScene then
            self._curScene = CU.GameObject.Instantiate(self.ImageScene, self.Scene.transform, false)
            self._curScene:SetActive(true)
            if d and d.image then
                bee.setIcon(self._curScene, d.image, true)
            end
        end
        if trans and self._curData.fadeInDt and self._curData.fadeInDt > 0 then
            self.ImageSceneTrans:SetActive(true)
            local cmp = self.ImageSceneTrans:GetComponent("Image")
            cmp.color = CU.Color(0, 0, 0, 1)
            bee.tween(self.ImageSceneTrans)
            : to(self._curData.fadeInDt, {opacity = 0})
            : call(function()
                self.ImageSceneTrans:SetActive(false)
            end)
            : ease(DT.Ease.Linear)
            : link()
        else
            self.ImageSceneTrans:SetActive(false)
        end
    end
end

function P:evt_story_try_auto_next()
    if self._isAutoPlay then
        self:onBtNextClick()
    end
end

function P:onUpdate(dt)
    if self._curNode then
        self._curNode:onUpdate(dt)
    end
end

