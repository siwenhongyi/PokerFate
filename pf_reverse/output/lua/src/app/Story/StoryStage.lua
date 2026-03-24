local StoryNode = require("app.story.StoryNode")
local P = class("StoryStage", UiBase)

-- 剧情点
function P:onAwake()
    self.ImageBg = self:find("ImageBg")
    self.BgTrigger = self:find("BgTrigger")
    self.UnlockEff = self:find("BgTrigger/UnLockEff")
    self.BtTrigger = self:find("BgTrigger/BtTrigger")
    self.BtTriggerIcon = self:find("BgTrigger/BtTrigger/Icon")
    self.starNum = self:find("BgTrigger/BtTrigger/ImageStar/TextNum")

    bee.addClick(self.BtTrigger, function()
        if PlayerModel:getCurLevel() == 2 and StoryModel:getDonesCount() == 1 then
            LogEx:log_newuser_log(10020310)
        elseif PlayerModel:getCurLevel() == 2 and StoryModel:getDonesCount() == 2 then
            LogEx:log_newuser_log(10020501)
        elseif PlayerModel:getCurLevel() == 3 and StoryModel:getDonesCount() == 2 then
            LogEx:log_newuser_log(10030201)
        elseif PlayerModel:getCurLevel() == 4 and StoryModel:getDonesCount() == 3 then
            LogEx:log_newuser_log(10040201)
        elseif PlayerModel:getCurLevel() == 6 and StoryModel:getDonesCount() == 4 then
            LogEx:log_newuser_log(10060201)
        elseif PlayerModel:getCurLevel() == 8 and StoryModel:getDonesCount() == 5 then
            LogEx:log_newuser_log(10080020)
        elseif PlayerModel:getCurLevel() == 10 and StoryModel:getDonesCount() == 6 then
            LogEx:log_newuser_log(10100201)
        elseif PlayerModel:getCurLevel() == 10 and StoryModel:getDonesCount() == 0 then
            LogEx:log_newuser_log(10100521)
        elseif PlayerModel:getCurLevel() == 11 and StoryModel:getDonesCount() == 0 then
            LogEx:log_newuser_log(10110201)
        end

        if bee.checkCd("StoryStage", 2) then
            self:onTrigger()
        end
    end)

    self._curStage = nil    -- 当前正在播放的剧情
    self._curNodeIndex = 0  -- 当前播放的剧情节点序号
    self._curNode = nil     -- 正在播放的 StrageNode 对象

    -- self._roles = {}
end

function P:setParams(params)
    P.super.setParams(self, params)

    self._curStage = params.stage
    self._storyLayer = params.storyLayer
    self._data = tpl_storyStage[self._curStage.id]
end

function P:onShow()
end

function P:onTrigger(isAuto)
    bee.emit("evt_onStageTrigger")
    RedManager:removeTag(RedTag.StoryBtn, self._data.id)
    self._curNodeIndex = 0
    self._storyLayer:onPlayStage(self, isAuto)
end

function P:startPlayNode()
    self.BgTrigger:SetActive(false)
    self:playNextNode()
end

function P:playNextNode(isSkip)
    if self._curStage and self._curStage.nodes then
        self._curNodeIndex = self._curNodeIndex + 1
        local node = self._curStage.nodes[self._curNodeIndex]
        if node then
            self._curNode = StoryNode:create(node)
            self._curNode:onEvent(self, self._storyLayer, isSkip)
        else
            self._curNode = nil
            
            self._storyLayer:onPlayStageEnd(self)
            UiManager:hideUI("StoryTalkDialog")
            -- bee.emit("evt_stageEnd")
        end
    end
end

function P:refreshStage()
    self.BgTrigger:SetActive(false)
    if "" ~= self._curStage.trigger.icon then
        bee.setIconInAtlas(self.BtTriggerIcon, self._curStage.trigger.icon, true)
        -- self.BtTrigger.transform.sizeDelta = self.BtTriggerIcon.transform.sizeDelta
    end
    self.BgTrigger.transform.localPosition = bee.v3(self._curStage.trigger.position.x, self._curStage.trigger.position.y)

    if self._data then
        bee.setText(self.starNum, self._data.star)
    end

    if self._curStage.objs then
        for _, v in ipairs(self._curStage.objs) do
            self._storyLayer:createRole(v)
        end
    end

    if self._curStage.trigger.ival and self._curStage.trigger.ival > 0 and not self._storyLayer._inEdit then
        self:once(0.5, function()
            self:onTrigger(true)
        end)
    end
end

function P:switchToStage(index)
    self._curNode = nil
    
    self._storyLayer:onPlayStageEnd(self)
    UiManager:hideUI("StoryTalkDialog")
end

function P:onStageEnter(isAnim)
    if self:checkIsFirstStage() then
        self._storyLayer:resetCamera(self._data.episode)
    end
    self.BgTrigger:SetActive(true)
    if isAnim then
        self.BgTrigger.transform.localScale = bee.v3()
        bee.tween(self.BgTrigger)
        : to(0.3, {scale = bee.v3(1, 1, 1)})
        : ease(DT.Ease.OutBack)
        : link()
    else
        self.BgTrigger.transform.localScale = bee.v3(1, 1, 1)
    end

    local count = ItemModel:getPropCount(GPropId.Star)
    if self._data and self._data.star then
        self.UnlockEff:SetActive(count >= self._data.star)
    end
end

function P:onStageExit()
    self.BgTrigger:SetActive(false)
end

function P:onStageSkip()
    while self._curNode do
        self:playNextNode(true)
    end
end

-- 执行下个动作
function P:onNextNode(e)
    if e and e.checkCb then
        local node = self._curStage.nodes[self._curNodeIndex + 1]
        if e.checkCb(node) then -- 检查是否可以进入下个节点，如果返回 true 则不进入
            return
        end
    end
    self:playNextNode()
end

function P:checkIsLastStage()
    local episodeDatas = StoryModel:getStageDatas(self._data.episode)
    return self._curStage.id == episodeDatas[#episodeDatas].id
end

function P:checkIsFirstStage()
    if self._data and self._curStage then
        local episodeDatas = StoryModel:getStageDatas(self._data.episode)
        return self._curStage.id == episodeDatas[1].id
    end
    return false
end

function P:onUpdate(dt)
    if self._curNode then
        self._curNode:onUpdate(dt)
    end
end

function P:switchRoleShow(bool)
    if self._storyLayer then
        self._storyLayer:switchRoleShow(bool)
    end
end

function P:getStageVersion()
    if self._curStage then
        return self._curStage.version or 1
    end
    return 1
end

return P
