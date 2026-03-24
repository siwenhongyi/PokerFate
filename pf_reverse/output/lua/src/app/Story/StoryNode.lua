local P = class("StoryNode")

-- 故事剧情节点

local TEXT_SPD = 0.1

function P:ctor(data)
    self._data = data   -- 节点数据
end

-- isSkip 跳过 isFast 快速显示
function P:onEvent(ctx, isSkip, isFast)
    self._ctx = ctx;
    self._et = 0
    self._dt = 0
    self._waitDt = 0
    self._autoNext = nil
    -- print("[Story] onEvent node " .. self._data.kind, json.encode(self._data))

    if self._data.kind == 1001 then --		背景切换
        ctx:switchScene(self._data, isSkip)
        if isSkip then
            ctx:playNextNode()
        else
            if self._data.trans ~= 0 then
                self._dt = self._data.dt or 1
            end
            self._autoNext = true
        end
    elseif self._data.kind == 2001 then --		人物对话
        if self._data.useName then
            self._text = _F(self._data.text or "", PlayerModel:getName())
        else
            self._text = _T(self._data.text or "")
        end
        if 2 == self._data.showType or isSkip or isFast then
            ctx:showTalk(self._data, self._text, true)
        else
            self._textSpd = self._data.showSpeed * TEXT_SPD
            if self._textSpd > 0 then
                self._textList = self:getTalkTextList(self._text)
                self._textLen = self:getTextListLen()
                self._dt = self._textLen * self._textSpd
                self._spd, self._textIndex = self._textSpd, 0
                ctx:showTalk(self._data, "")
            else
                ctx:showTalk(self._data, self._text)
            end
        end
        if self._data.face then
            ctx:playRoleFace(self._data)
        end
        if isSkip then
            ctx:playNextNode()
        elseif self._data.voice and self._data.voice ~= "" then
            self._waitDt = ctx:playSound(self._data)
        end
    elseif self._data.kind == 2002 then --		人物出现
        ctx:createRole(self._data, nil, isSkip)
        if isSkip then
            ctx:playNextNode()
        else
            self._dt = math.max(self._data.fadeInDt, self._data.moveDt)
            if self._dt > 0 then
                self._autoNext = true
            else
                ctx:playNextNode()
            end
        end
    elseif self._data.kind == 2003 then --		人物消失
        ctx:removeRole(self._data, isSkip)
        if isSkip then
            ctx:playNextNode()
        else
            self._dt = self._data.fadeOutDt
            if self._dt > 0 then
                self._autoNext = true
            else
                ctx:playNextNode()
            end
        end
    elseif self._data.kind == 2004 then --		人物表情更换
        ctx:playRoleFace(self._data)
        ctx:playNextNode()
    elseif self._data.kind == 2005 then --		人物动作更换
        ctx:playRoleAnim(self._data)
        ctx:playNextNode()
    elseif self._data.kind == 2006 then --		气泡表情
        ctx:playSign(self._data)
        ctx:playNextNode()
    elseif self._data.kind == 2007 then --		清空对话框
        self._ctx.Dialog:SetActive(false)
        self._ctx.TextCG:SetActive(false)
        ctx:playNextNode()
    elseif self._data.kind == 2008 then --		角色置灰
        ctx:setRoleGray(self._data)
        ctx:playNextNode()
    elseif self._data.kind == 3001 then --		切换BGM
        ctx:playBGM(self._data)
        ctx:playNextNode()
    elseif self._data.kind == 3002 then --		BGM暂停
        ctx:pauseBGM(self._data)
        ctx:playNextNode()
    elseif self._data.kind == 3003 then --		BGM继续播放
        ctx:resumeBGM(self._data)
        ctx:playNextNode()
    elseif self._data.kind == 3004 then --		音效播放
        ctx:playSound(self._data)
        ctx:playNextNode()
    elseif self._data.kind == 3005 then --		声音清除
        ctx:clearSound(self._data)
        ctx:playNextNode()
    elseif self._data.kind == 4001 then --		界面UI显隐
        ctx:hideShowUI(self._data)
        if isSkip or not self._data.fade then
            ctx:playNextNode()
        else
            if self._data.showType == 0 or self._data.showType == 3 then
                self._dt = 0.2
            else
                self._dt = 0.1
            end
            self._autoNext = true
        end
    elseif self._data.kind == 4002 then --		选项
        if isSkip then
            ctx:playNextNode()
        else
            ctx:showOptions(self._data)
        end
    elseif self._data.kind == 9001 then --		计时器
        if isSkip then
            ctx:playNextNode()
        else
            self._dt = self._data.dt
            self._autoNext = self._data.triType == 0
        end
    elseif self._data.kind == 9002 then --		名称输入
        if isSkip then
            ctx:playNextNode()
        else
            self._dt = 2
            UiManager:showUI("GuideChangeName", {hideCb = function()
                ctx:playNextNode()
            end})
        end
    end
    if 0 == self._waitDt and self._dt > 0.5 then
        self._waitDt = self._dt + 0.5
    end
end

function P:onExit()
    if self._data.kind == 2001 then
        self._ctx:showDialog(false, self._data.fadeOut)
        self._ctx.TextCG:SetActive(false)
        -- self._ctx:setRolesGray(false)
    end
end

-- 被点击，如果返回 true 则表示拦截执行下一步的步骤
function P:onClick()
    if self._data.kind == 9002 then
        return true
    end
    if self._data.kind == 2001 and self._data.showType == 0 and not self:isOver() then
        self._et = self._dt
        self._ctx:showTalk(self._data, self._text, true)
        return true
    elseif self._data.kind == 4002 then
        return true
    end
    return false
end

function P:isOver()
    return self._et >= self._dt
end

function P:getTextListSub(index)
    local ret = ""
    for _, v in ipairs(self._textList) do
        if v.text then
            local len = string.utf8len(v.text)
            if index <= len then
                ret = ret .. (v.tag1 or "") .. string.utf8sub(v.text, 0, index) .. (v.tag2 or "")
                break
            else
                index = index - len
                ret = ret .. (v.tag1 or "") .. v.text .. (v.tag2 or "")
            end
        end
    end
    return ret
end

function P:getTextListLen()
    local ret = 0
    for _, v in ipairs(self._textList) do
        if v.text then
            ret = ret + string.utf8len(v.text)
        end
    end
    return ret
end

-- 获取对话文本的富文本显示列表
function P:getTalkTextList(text)
    local textList = {}

    local i, textStart = 1, 1
    while i <= #text do
        if string.byte(text, i) == 60 then
            local j = string.find(text, ">", i)
            if j then
                if textStart < i then
                    table.insert(textList, {text = string.sub(text, textStart, i - 1)})
                end
                local tag = string.sub(text, i, j)
                if string.byte(text, i + 1) == 47 then
                    local tagName = string.sub(tag, 3, -2)
                    table.insert(textList, {tag2 = tag, tagName = tagName})
                else
                    local tagName = string.sub(tag, 2, string.find(tag, "=") - 1)
                    table.insert(textList, {tag1 = tag, tagName = tagName})
                end
                i = j + 1
                textStart = i
            else
                i = i + 1
            end
        else
            i = i + 1
        end
    end
    if textStart < #text then
        table.insert(textList, {text = string.sub(text, textStart)})
    end
    local function parseTag(retList, dom, textList, idx, parentTags)
        local v = textList[idx]
        if not v then
            return
        end
        if not parentTags then
            parentTags = {}
        end
        if v.text then
            if not dom or dom.text then
                dom = {}
                retList[#retList + 1] = dom
            end
            dom.text = v.text
            return parseTag(retList, dom, textList, idx + 1, parentTags)
        elseif v.tag1 then
            local newDom = {
                tag1 = "",
                tagName = v.tagName,
            }
            for _, tv in ipairs(parentTags) do
                newDom.tag1 = newDom.tag1 .. tv.tag1
            end
            newDom.tag1 = newDom.tag1 .. v.tag1
            retList[#retList + 1] = newDom
            for i = idx + 1, #textList do
                local nv = textList[i]
                if nv.tag2 and nv.tagName == v.tagName then
                    newDom.tag2 = nv.tag2
                    for i = #parentTags, 1, -1 do
                        newDom.tag2 = newDom.tag2 .. parentTags[i].tag2
                    end
                    parentTags[#parentTags + 1] = {tag1 = v.tag1, tag2 = nv.tag2, tagName = v.tagName}
                    break
                end
            end
            return parseTag(retList, newDom, textList, idx + 1, parentTags)
        elseif v.tag2 then
            for i = #parentTags, 1, -1 do
                if parentTags[i].tagName == v.tagName then
                    table.remove(parentTags, i)
                    break
                end
            end
            return parseTag(retList, dom, textList, idx + 1, parentTags)
        end
        return idx + 1
    end
    
    local retList = {}
    parseTag(retList, nil, textList, 1)
    return retList
end

function P:onUpdate(dt)
    if self._et < self._dt or self._et < self._waitDt then
        self._et = self._et + dt
    end
    if self._data.kind == 2001 and self._data.showType ~= 2 and not self:isOver() then
        self._spd = self._spd + dt
        while self._spd >= self._textSpd do
            self._spd = self._spd - self._textSpd
            self._textIndex = self._textIndex + 1
            -- local subText = string.utf8sub(self._text, 0, self._textIndex)
            subText = self:getTextListSub(self._textIndex)
            self._ctx:showTalk(self._data, subText, self._textIndex >= self._textLen)
        end
    end
    if self:isOver() then
        if self._data.cb then
            self._data.cb()
            self._data.cb = nil
        end
        if self._autoNext or self._ctx:isStoryOver() then
            self._ctx:playNextNode()
        elseif self._et >= self._waitDt then
            bee.emit("evt_story_try_auto_next")
        end
    end
end

