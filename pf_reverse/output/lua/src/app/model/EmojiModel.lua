local P = class("EmojiModel", BaseModel)
EmojiModel = P

function P:ctor()
    P.super.ctor(self)

    --免费次数
    self.freeTimes = 0
    --接收的对象
    self.receiveId = 0
    
    --背包表情Tag
    self.bagTag = nil
    --局内表情Tag
    self.tableTags = {}
    --局内表情Tween
    self.tableTweens = {}

    --是否在交互模式中
    self.isInteractionMode = false

    --座位偏移
    self.seatOffsetPos = {
        [1] = {0, 10},
        [2] = {0, 0},
        [3] = {0, 0},
        [4] = {-40, 0},
        [5] = {-40, 10},
        [6] = {-20, 30},
    }
end

-- function P:checkCost(costId, needCount)
--     local costRemainCount = ItemModel:getItemNumById(costId)
-- end

function P:evt_SelfUserInfoRSP(msg)
	self.freeTimes = msg.emoji_free_times
    -- self.freeTimes = 1
end

function P:SendEmoji(emojiId, toUid)
    self.receiveId = toUid
    local rags = {id = emojiId, to_uid = toUid}
    -- bee.emit("evt_sendEmojiCallback")
    -- bee.emit("evt_EmojiBRC", {uid = PlayerModel:getUid(), to_uid = toUid, id = emojiId})
    Net:sendReq("pb.SendEmojiREQ", rags)
end
function P:evt_SendEmojiRSP(msg)
    bee.logEvent("ingame-emoji-send-new", GameModel.data:getGameType(), GameModel.data:getRoomId(), self.receiveId, msg.code == 0 and 1 or 2)
    if msg.code ~= 0 then
        return
    end

    self.freeTimes = msg.emoji_free_times
    -- self.freeTimes = self.freeTimes - 1
    -- if self.freeTimes < 0 then
    --     self.freeTimes = 0
    -- end
    bee.emit("evt_sendEmojiCallback")
end

--文件名转换
function P:exchangeName(str)
    if not str or str == "" then
        return ""
    end
    
    local result = str:gsub("(%u)", "_%1"):lower()
    -- 去除开头的下划线
    if result:sub(1, 1) == "_" then
        result = result:sub(2)
    end
    return result
end

--展示表情
function P:showEmojiInDisplay(img, cfg, target)
    if cfg.type == 1 then
        self:display1(img, cfg, target)
    elseif cfg.type == 2 then
        self:display2(img, cfg, target)
    end
end
function P:display1(img, cfg, target)
    local resname = string.replace(cfg.name, "01", "%02d")
    local image = img:GetComponent("Image")
    local length = cfg.receives[2]
    local curLen = 1
    local fileName = ""
    local interval = cfg.interval * 0.001

    image.sprite = ResManager:GetSprite(cfg.name)
    image:SetNativeSize()

    self:clearBagEmojiTag()
    self.bagTag = bee.schedule(interval, function ()
        fileName = string.format(resname, curLen)
        image.sprite = ResManager:GetSprite(fileName)
        
        curLen = curLen + 1
        if curLen > length then
            curLen = 1
        end
    end, target)
end
function P:display2(img, cfg, target)
    local resname1 = string.replace(cfg.name, "01", "%02d")
    local resname2 = string.replace(cfg.name2, "01", "%02d")
    local image = img:GetComponent("Image")
    local length1 = cfg.sends[2]
    local length2 = cfg.receives[2]
    local curLen = 1
    local fileName = ""
    local interval = cfg.interval * 0.001
    local stage = 1

    image.sprite = ResManager:GetSprite(cfg.name)
    image:SetNativeSize()

    self:clearBagEmojiTag()
    self.bagTag = bee.schedule(interval, function ()
        if stage == 1 then
            fileName = string.format(resname1, curLen)
            image.sprite = ResManager:GetSprite(fileName)
            curLen = curLen + 1
            if curLen > length1 then
                curLen = 1
                stage = 2
            end
        else
            fileName = string.format(resname2, curLen)
            image.sprite = ResManager:GetSprite(fileName)
            curLen = curLen + 1
            if curLen > length2 then
                curLen = 1
                stage = 1
            end
        end
    end, target)
end

function P:clearBagEmojiTag()
    if self.bagTag ~= nil then
        scheduler:removeTag(self.bagTag)
        self.bagTag = nil
    end
end

function P:evt_backpackToggleOff()
    self:clearBagEmojiTag()
end

--局内播放表情
function P:playEmoji(obj, sendPos, receivePos, id)
    local cfg = tpl_table_emoji[id]
    if cfg.type == 1 then
        self:play1(cfg, obj, sendPos, receivePos)
    else
        self:play2(cfg, obj, sendPos, receivePos)
    end
end
function P:play1(cfg, obj, sendPos, receivePos)
    local resname = string.replace(cfg.name, "01", "%02d")
    obj.transform.localScale = bee.v3one * 0.8
    local image = obj:GetComponent("Image")
    image.sprite = ResManager:GetSprite(cfg.name)
    image:SetNativeSize()
    image.transform.position = sendPos
    -- local length = cfg.receives[2]
    local curLen = 1
    local fileName = ""
    local interval = cfg.interval * 0.001
    local stage = 1
    local flyFrames = cfg.flys and #cfg.flys > 0
    local flyTime = cfg.fly_time and (cfg.fly_time * 0.001) or ((cfg.flys[2] - cfg.flys[1]) * interval)
    local curFlyTime = 0
    local flyStage = false
    local loopTimes = cfg.receive_loop and cfg.receive_loop[3] or 0

    local tag
    tag = bee.schedule(interval, function ()
        fileName = string.format(resname, curLen)
        image.sprite = ResManager:GetSprite(fileName)
        
        if stage == 1 then
            curLen = curLen + 1
            if curLen > cfg.sends[2] then
                stage = 2
                curFlyTime = 0
            end
        elseif stage == 2 then
            if not flyStage then
                flyStage = true
                local tween = bee.Tween.toVector(sendPos, receivePos, flyTime, function(v)
                    image.transform.position = v
                end)
                self.tableTweens[tag] = tween
            end
            curFlyTime = curFlyTime + interval

            if flyFrames and curLen < cfg.flys[2] then
                curLen = curLen + 1
            end

            if curFlyTime > flyTime then
                stage = 3
                self.tableTweens[tag]:Kill()
                self.tableTweens[tag] = nil
            end
        else
            curLen = curLen + 1
            if curLen > cfg.receives[2] then
                if loopTimes <= 0 then
                    scheduler:removeTag(tag)
                    table.removebyvalue(self.tableTags, tag)
                    CU.GameObject.Destroy(obj)
                else
                    loopTimes = loopTimes - 1
                    curLen = cfg.receive_loop[1]
                end
            end
        end
    end, obj)
    table.insert(self.tableTags, tag)
end

function P:play2(cfg, obj, sendPos, receivePos)
    local resname = string.replace(cfg.name, "01", "%02d")
    obj.transform.localScale = bee.v3one * 0.8
    local image = obj:GetComponent("Image")
    image.sprite = ResManager:GetSprite(cfg.name)
    image:SetNativeSize()
    image.transform.position = sendPos

    local resname2 = string.replace(cfg.name2, "01", "%02d")
    local obj2 = CU.GameObject.Instantiate(obj, obj.transform.parent, false)
    obj2.transform.localScale = bee.v3one * 0.8
    local image2 = obj2:GetComponent("Image")
    image2.sprite = ResManager:GetSprite(cfg.name2)
    image2:SetNativeSize()
    obj2:SetActive(false)
    image2.transform.position = receivePos

    local curLen = 1
    local fileName = ""
    local over = false
    local curLen2 = 1
    local fileName2 = ""
    local over2 = false
    local stage = 1
    local interval = cfg.interval * 0.001
    local waitTime = cfg.fly_time * 0.001
    local curWaitTime = 0

    local tag
    tag = bee.schedule(interval, function ()
        if curLen <= cfg.sends[2] then
            fileName = string.format(resname, curLen)
            image.sprite = ResManager:GetSprite(fileName)
        end
        if curWaitTime > waitTime then
            fileName2 = string.format(resname2, curLen2)
            image2.sprite = ResManager:GetSprite(fileName2)
        end

        curLen = curLen + 1
        if stage == 1 then
            curWaitTime = curWaitTime + interval
            if curWaitTime > waitTime then
                stage = 2
                obj2:SetActive(true)
            end
        elseif stage == 2 then
            curLen2 = curLen2 + 1
            if curLen > cfg.sends[2] then
                obj:SetActive(false)
                over = true
            end
            if curLen2 > cfg.receives[2] then
                obj2:SetActive(false)
                over2 = true
            end
            if over and over2 then
                scheduler:removeTag(tag)
                table.removebyvalue(self.tableTags, tag)
                CU.GameObject.Destroy(obj)
                CU.GameObject.Destroy(obj2)
            end
        end
    end, obj)
    table.insert(self.tableTags, tag)
end

function P:evt_LeaveRoomRSP()
    for _,v in pairs(self.tableTweens) do
        self.tableTweens[v]:Kill()
    end
    self.tableTweens = {}
    for _,v in pairs(self.tableTags) do
        scheduler:removeTag(v)
    end
    self.tableTags = {}
end

function P:resetFreeTimes()
    self.freeTimes = tpl_constdata.Table_Emoji_Free_Num
end

function P:checkEnoughItem(emojiId, tipLab)
    local emojiCfg = tpl_table_emoji[emojiId]
    local costId = emojiCfg.item[1]
    local costNeedCount = emojiCfg.item[2]
    local costRemainCount = ItemModel:getItemNumById(costId)
    local enough = costRemainCount >= costNeedCount
    if tipLab and not enough then
        UiManager:showToast(_F(tipLab, _T(tpl_props[costId].name)))
    end
    return enough
end

function P:changeInteractionMode(value)
    self.isInteractionMode = value
end

return P