local P = {
    curStep = -1,    -- 当前存档点
    curGuide = nil,   -- 当前引导数据
    sysGuideIds = {},  --系统引导存储记录
}
GuideManager = P

function P:init()
    
end

function P:startGuide(id)
    if id then
        for _, v in ipairs(tpl_guide_list) do
            if v.guide_type == 1 and v.guide == id then
                self.curGuide = v
                break
            end
        end
    else
        for _, v in ipairs(tpl_guide_list) do
            if v.guide_type == 1 and v.guide > self.curStep then
                self.curGuide = v
                break
            end
        end
    end

    local v = self.curGuide
    if self.curGuide and self.curGuide.start_event then
        bee.emit(self.curGuide.start_event)
    end
    bee.logEvent("guide-id", v.id)
    if GuideKind.Story == v.kind then
        UiManager:showUI("Story", {id = v.story_id, index = v.story_index})
    elseif GuideKind.UI == v.kind then
        UiManager:showUI("GameGuide", {guide = v.guide})
    elseif GuideKind.Draw == v.kind then
        GachaModel:showWheelAnim(CARD_CONTENT_TYPE.CHARACTER, function()
            UiManager:showUI("GachaResultShow", {showList = {{
                major_type = GMajorType.ROLE,
                new = true,
                id = 1001,
            }}, closeCb = function()
                UiManager:showUI("GachaResult", {isGuide = true, num = 1, list = {{
                    content_type = CARD_CONTENT_TYPE.CHARACTER,
                    content_id = 1001,
                    weight = 3000,
                    weight_up = true,
                    new = true,
                }}, hideCb = function()
                    self:doGuideEnd()
                end})
            end})
        end)
    end

    if id == 1 then
        SdkHelper:sentAdjustEvent("b3f3fs")
        SdkHelper:sendFirebaseEvent("tutorial_begin")
    end
end

-- 开始系统引导
function P:startSystemGuide(id, delay)
    local guideId = self:isSysGuideValid(id)
    if guideId == 0 then
        return false
    end

    local d = tpl_guide[guideId]
    if d and d.start_event then
        bee.emit(d.start_event)
    end
    self.curGuide = d
    bee.emit(EventDef.evt_sys_guide_start, self.curGuide)
    if d and not UiManager:getUI("GameGuide") then
        UiManager:showUI("GameGuide", {data = d, delay = delay, sid = guideId})
        bee.logEvent("guide-id-trigger", guideId)
        Net:post("player/reportGuide", {guide_id = guideId}, function()
            self:changeSysGuideId(guideId)
        end)
        return true
    end
    return false
end

-- 检查是否要进行新手引导
function P:checkGuide()
    if -1 == self.curStep then
        return false
    elseif 0 == self.curStep then
        return true
    else
        for i = #tpl_guide_list, 1, -1 do
            local v = tpl_guide_list[i]
            if v.guide_type == 1 and v.guide > self.curStep then
                return true
            end
        end
    end
    return false
end

function P:isInGuide()
    return self.curGuide ~= nil
end

function P:setCurStep(step)
    self.curStep = step
end

function P:setCurGuide(guide)
    self.curGuide = guide
    if self.curGuide and self.curGuide.start_event then
        bee.emit(self.curGuide.start_event)
    end
end

-- 当前引导结束
function P:doGuideEnd()
    if self.curGuide and self.curGuide.guide_type == 1 then
        if self.curGuide.guide == 1010 then
            self.curStep = self.curGuide.guide + 1
            Net:sendReq("pb.SetNewerGuideStepREQ", {step = self.curGuide.guide + 1})
            bee.logEvent("guide-id", 2)
        else
            self.curStep = self.curGuide.guide
            Net:sendReq("pb.SetNewerGuideStepREQ", {step = self.curGuide.guide})
        end
        if self.curGuide.stop_event then
            bee.emit(self.curGuide.stop_event)
            if self.curGuide.stop_event == "evt_try_auto_pop" then
                -- SdkHelper:sendFbEvent("tutorial_complete")
                SdkHelper:sendFbEvent("fb_mobile_tutorial_completion")
                SdkHelper:sentAdjustEvent("2z18wp")
                SdkHelper:sendFirebaseEvent("tutorial_complete")
            end
        end
        self.curGuide = nil
        if self:checkGuide() then
            self:startGuide()
            return true
        end
    elseif self.curGuide and self.curGuide.guide_type == 2 then
        bee.emit(EventDef.evt_sys_guide_end, self.curGuide)
        self.curGuide = nil
    end
    return false
end

-- 完成当前引导步骤，给起名弹窗使用的
function P:doGuideStep()
    if self.curGuide and self.curStep < self.curGuide.guide then
        Net:sendReq("pb.SetNewerGuideStepREQ", {step = self.curGuide.guide})
    end
end

--获取系统引导id
function P:getSystemGuides()
    Net:post("player/guideList", nil, function(data)
        if data.code == 0 then
            self.sysGuideIds = data.list or {}
            -- self.sysGuideIds = {}
        end
    end)
end

function P:isSysGuideValid(id)
    if not id then return 0 end
    local d = tpl_guide[id]
    if not d or not self:checkTime(d) then
        return 0
    end
    return self:checkGuideId(d, id)
end

--系统引导存储记录变更
function P:changeSysGuideId(id)
    table.insert(self.sysGuideIds, id)
end

--时间判定
function P:checkTime(cfg)
    if cfg.effective_time == nil then
        return true
    end
        -- return true
    if cfg.guide_old == nil then
        return PlayerModel:getRegisterTime() > cfg.effective_time
    else
        return true
    end
end

--新旧引导判定
function P:checkGuideId(cfg, id)
    if cfg.guide_old ~= nil and PlayerModel:getRegisterTime() < cfg.effective_time then
        if table.keyof(self.sysGuideIds, cfg.guide_old) then
            return 0
        end
        return cfg.guide_old
    end

    if table.keyof(self.sysGuideIds, id) then
        return 0
    end
    return id

    -- if cfg.guide_old == nil then
    --     if table.keyof(self.sysGuideIds, id) then
    --         return false
    --     end
    --     return true
    -- else
    --     if table.keyof(self.sysGuideIds, cfg.guide_old) then
    --         return false
    --     elseif table.keyof(self.sysGuideIds, id) then
    --         return false
    --     end
    --     return true
    -- end
end

return P