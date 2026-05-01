-- spine 帮助类

bee.Spine = {
    objs = {},  -- 游戏物体和 spine 对象的map, {GameObject = spine}

    -- 清除 obj
    clear = function(obj)
        bee.Spine.objs[obj] = nil
    end,

    -- 清空 objs
    clearAll = function()
        bee.Spine.objs = {}
    end,

    clearNull = function()
        for k, v in pairs(bee.Spine.objs) do
            if bee.isNull(k) then
                bee.Spine.objs[k] = nil
            end
        end
    end,
}

--SkeletonAnimation 的方式实例化
function bee.spineAnim(obj)
	local o = bee.Spine.objs[obj]
	if not o then
        local cmp = obj:GetComponent("SkeletonAnimation")
        if not cmp then
            return nil
        end
		o = {
			obj = obj,
            cmp = cmp,
			anim = cmp.AnimationState,
			startCb = nil,
			completeCb = nil,
		}

		setmetatable(o, {__index = bee._spineMeta})
        bee.Spine.objs[obj] = o
	end

	return o
end

--SkeletonGraphic 的方式实例化
function bee.spine(obj)
    local o = bee.Spine.objs[obj]
    if not o then
		local skg=obj:GetComponent("SkeletonGraphic")
        if not skg then
            return nil
        end
        o = {
            obj = obj,
			cmp = skg,
			anim = skg.AnimationState,
            startCb = nil,
            completeCb = nil,
        }

        setmetatable(o, {__index = bee._spineMeta})
        bee.Spine.objs[obj] = o
    end

    return o
end

bee._spineMeta = {
    -- 播放动画
    play = function(o, name, loop)
        o.name = name
        o.anim:SetAnimation(0, name, loop or false)
        return o
    end,

    -- 播放动画，返回 Entry
    play2 = function(o, name, loop)
        o.name = name
        return o.anim:SetAnimation(0, name, loop or false)
    end,

    playAtTrack = function(o, trackIndex, name, loop)
        o.name = name
        return o.anim:SetAnimation(trackIndex, name, loop or false)
    end,
	
    --停止播放spine动画
	stopAnim = function(o)
		o.anim:SetEmptyAnimation(0, 0.1)
        return o
	end,
	
	--暂停播放spine动画
	pauseAnim = function(o)
		o.cmp.timeScale = 0
	end,

    --继续播放spine动画
    resumeAnim = function(o)
        o.cmp.timeScale = 1
    end,

    -- 是否存在动画
    isHaveAnim = function (o, name)
        return nil ~= o.anim.Data.SkeletonData:FindAnimation(name)
    end,

    clearTracks = function (o, name)
		o.anim:ClearTracks()
        return o
    end,

    setTimeScale = function(o, speed)
        o.cmp.timeScale = speed
        return o
    end,

    getSkin = function(o, name)
        return o.cmp.Skeleton.Data:FindSkin(name)
    end,

    setSkin = function(o, name, noInit)
        if not noInit then
            o.cmp.Skeleton.Skin = nil
        end
        o.cmp.Skeleton:SetSkin(name)
        if not noInit then
            o.cmp.Skeleton:SetToSetupPose()
        end
        return o
    end,

    resetSkin = function(o)
        o.cmp.Skeleton:SetToSetupPose()
        return o
    end,

    -- 绑定皮肤
    attachSkin = function(o, name)
        CS.SpineHelper.AttachSkinAttachment(o.cmp, name)
        return o
    end,

    -- 移除绑定皮肤
    removeAttachSkin = function(o, name)
        CS.SpineHelper.RemoveSkinAttachment(o.cmp, name)
        return o
    end,

    -- 设置显示部件
    setAttachment = function(o, slotName, attachmentName, skinName)
        if not attachmentName then
            o:removeAttachment(slotName)
        elseif skinName then
            local slot = o.cmp.Skeleton:FindSlot(slotName)
            if slot then
                local skin = o.cmp.Skeleton.Data:FindSkin(skinName)
                if skin then
                    local attachment = skin:GetAttachment(slot.Data.Index, attachmentName)
                    if attachment then
                        slot.Attachment = attachment
                    end
                end
            end
        else
            o.cmp.Skeleton:SetAttachment(slotName, attachmentName)
        end
        return o
    end,

    setSlotAlatsAttachment = function(o, slotName, atlasName, imgName)
        CS.SpineHelper.SetSlotAlatsAttachment(o.cmp, slotName, atlasName, imgName)
        return o
    end,

    removeAllAttachment = function(o)
        CS.SpineHelper.RemoveAllAttachment(o.cmp)
        return o
    end,

    removeAttachment = function(o, name)
        CS.SpineHelper.RemoveAttachment(o.cmp, name)
        return o
    end,

    -- 完成回调 cb(entry)
    onComplete = function(o, cb)
        if not o._completeCb then
            o._completeCb = function(e)
                if o.completeCb and e:ToString() == o.name then
                    o.completeCb(e)
                end
            end
            o.anim:Complete("+", o._completeCb)
        end
        o.completeCb = cb
        return o
    end,

    -- 开始回调
    onStart = function(o, cb)
        if not o._startCb then
            o._startCb = function(e)
                if o.startCb then
                    o.startCb(e)
                end
            end
            o.anim:Start("+", o._startCb)
        end
        o.startCb = cb
        return o
    end,

    -- 清空事件
    clearEvent = function(o)
        if o.startCb then
            -- o.anim:Start("-", o.startCb)
            o.startCb = nil
        end
        if o.completeCb then
            -- o.anim:Complete("-", o.completeCb)
            o.completeCb = nil
        end
        return o
    end,

    -- 从 Spine.objs 中删除自己的数据
    delete = function(o)
        bee.Spine.objs[o.obj] = nil
        return o
    end,
}