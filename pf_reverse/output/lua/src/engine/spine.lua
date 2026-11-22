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

-- 每个 spine 组件实例上被隐藏的 slot（弱键：组件销毁后自动回收）
-- 这里刻意不改 SkeletonData：SkeletonData 由 SkeletonDataAsset 缓存、所有实例共享，
-- 改它会把使用同一资源的新实例（同类预制体、换装预览等）的特效也一起隐藏掉。
local _hideStates = setmetatable({}, { __mode = "k" })

-- 清掉本实例被隐藏 slot 的 attachment。
-- 只把 slot.Attachment 置 nil 是没用的：动画里的 AttachmentTimeline 每帧都会把它写回去，
-- 所以每帧都要在“动画已 Apply、世界变换还没算、网格还没生成”的时机再清一次，
-- UpdateLocal 正好是这个时机（SkeletonGraphic / SkeletonAnimation 都有该事件）。
local function _applyHiddenSlots(st)
	local items = st.items
	if not items then
		return
	end
	local indices = st.indices
	for i = 1, #indices do
		local slot = items[indices[i]]
		if slot and slot.Attachment then
			slot.Attachment = nil
		end
	end
end

-- 完整名匹配不上时按前缀匹配
local function _findSlots(skel, name)
	local slot = skel:FindSlot(name)
	if slot then
		return { slot }
	end
	local ret = {}
	local slots = skel.Slots
	for i = 0, slots.Count - 1 do
		local item = slots.Items[i]
		local itemName = item.Data.Name
		if itemName and string.sub(itemName, 1, #name) == name then
			ret[#ret + 1] = item
		end
	end
	return ret
end

-- 隐藏当前实例中指定 slot 的显示（含翻转书式特效 slot）
-- slotNames 支持完整 slot 名，也支持前缀（如 "2006_4_smoke/" 可一次匹配该前缀下的所有 slot）。
-- 只作用于传入的组件实例，不影响使用同一 SkeletonDataAsset 的其它实例。
-- 返回 restore()，调用后该实例恢复原样。
function bee.hideSpineSlots(cmp, slotNames)
	local skel = cmp and cmp.Skeleton
	if not skel or not slotNames then
		return function() end
	end

	local st = _hideStates[cmp]
	if not st then
		st = { indices = {}, has = {} }
		st.hook = function()
			_applyHiddenSlots(st)
		end
		_hideStates[cmp] = st
		cmp:UpdateLocal("+", st.hook)
	end
	-- Skeleton 可能被重建，每次调用都刷新一下引用
	st.skel = skel
	st.items = skel.Slots.Items

	local added, addedSlot = {}, {}
	for _, slotName in ipairs(slotNames) do
		for _, slot in ipairs(_findSlots(skel, slotName)) do
			local idx = slot.Data.Index
			if not st.has[idx] then
				st.has[idx] = true
				st.indices[#st.indices + 1] = idx
				added[#added + 1] = idx
				addedSlot[#addedSlot + 1] = slot
			end
		end
	end

	_applyHiddenSlots(st)

	return function()
		if #added == 0 then
			return
		end
		for i = 1, #added do
			local idx = added[i]
			st.has[idx] = nil
			for j = #st.indices, 1, -1 do
				if st.indices[j] == idx then
					table.remove(st.indices, j)
				end
			end
		end
		-- 立即把 setup pose 的 attachment 还回去（没有动画在跑时也能恢复显示）
		for i = 1, #addedSlot do
			local slot = addedSlot[i]
			local name = slot.Data.AttachmentName
			if name then
				skel:SetAttachment(slot.Data.Name, name)
			end
		end
		added, addedSlot = {}, {}

		if #st.indices == 0 then
			if st.hook then
				cmp.UpdateLocal("-", st.hook)
				st.hook = nil
			end
			st.skel, st.items = nil, nil
			if _hideStates[cmp] == st then
				_hideStates[cmp] = nil
			end
		end
	end
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

    -- 隐藏指定 slot 的显示（含翻转书式特效 slot），names 为 slot 名数组
    -- 只影响当前实例（不改共享 SkeletonData），可重复调用；返回 restore() 还原函数
    hideSlots = function(o, names)
        return bee.hideSpineSlots(o.cmp, names)
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