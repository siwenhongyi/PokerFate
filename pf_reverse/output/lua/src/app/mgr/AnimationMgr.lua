-- 动画管理
local P = {}

AnimationMgr = P


local completeCbs = {}

-- 点击特效
bee.on("evt_onMouseButtonDown", function(info)
	local eff = AnimationMgr:playUIEffect("Prefab/Eff_poker_click", UiManager:getUiRoot().transform, nil, 0.7)
	eff.transform.position = bee.v3(info.worldPos.x, info.worldPos.y, 0)
	eff.transform.localScale = bee.v3(1, 1, 1)
	eff.transform:SetAsLastSibling()
end)

function P:clearClickEffect()
	for i = UiManager:getUiRoot().transform.childCount, 1, -1 do
		if string.find(UiManager:getUiRoot().transform:GetChild(i - 1).name, "Eff_poker_click") then
			ObjectCache:putItem(UiManager:getUiRoot().transform:GetChild(i - 1).gameObject)
		end
	end
end

function P:playAnim(obj, name, callback, isLoop)
	self:playAnimator(obj:GetComponent("Animator"), name, callback, isLoop)
end

function P:playAnimator(animator, stateName, callback, isLoop)
	if bee.isNull(animator) then
		return 
	end

	local _time = CS.AnimatorManager.Instance:GetAnimationTimes(animator,stateName)
	if _time == 0 then
		print("不存在的动画", stateName)
		-- if animator~=nil and callback~=nil then
		-- 	callback(false)
		-- end
		-- return 
	end
	if isLoop then
		animator:Play(stateName)
		print("playAnimator isLoop",stateName,isLoop)
	else
		animator:Play(stateName, -1, 0)
	end

	-- 同一animator播放下一个动作时，移除上一个动作的回调
	if completeCbs[animator] and next(completeCbs[animator]) then
		for _, key in pairs(completeCbs[animator]) do
			scheduler:removeTag(key)
		end
	end
	completeCbs[animator] = {}

	if callback then
		table.insert(completeCbs[animator], bee.once(_time, function(time)
			if not bee.isNull(animator) and callback ~= nil then
				callback(true)
			end
		end))
	end
end

function P:play(animator, name, callback, node)
	if bee.isNull(animator) then return end
	animator:Play(name, -1, 0)
	if node then
		scheduler:removeTarget(node)
	end
	if callback then
    	local _time = CS.AnimatorManager.Instance:GetAnimationTimes(animator, name)
		bee.once(_time, callback, node)
	end
end

function P:playUIEffect(name, parent, localPos, autoRemoveDt, noCache,layer)
	if not name then
		return
	end
	local eft = ObjectCache:getItemWithName(name)
	if eft then
		if layer then
			eft.gameObject.layer=layer
			-- CS.Utils.SetAllChildLayer(eft.transform,layer)
			local cmps = eft.transform:GetComponentsInChildren(typeof(CS.UnityEngine.Transform), true)
			for i = 0, cmps.Length - 1 do
				cmps[i].gameObject.layer = layer
			end
		end
		eft.transform:SetParent(parent, false)
		if localPos then
			eft.transform.localPosition = localPos
		end
		if -1 ~= autoRemoveDt then
			if noCache then
				CU.GameObject.Destroy(eft, autoRemoveDt or 2)
			else
				ObjectCache:putItem(eft, autoRemoveDt or 2)
			end
		end
		return eft
	end
end

function P:PlayAllParticle(rootObj)
	CS.AnimatorManager.Instance:PlayAllChildParticle(rootObj)
end

function P:StopAllParticle(rootObj)
	CS.AnimatorManager.Instance:StopAllChildParticle(rootObj)
end


-- ============================ 预制动画 ============================

-- 直线飞行
--[[ params =
{
	time = 动画时间
	ease = 缓动效果
	delay = 延迟时间
	isShowTargetEft = 是否播放到达特效
}
--]]
-- targetPos：世界坐标
function P:playStraightFlight(obj, targetPos, callback, params)
	if bee.isNull(obj) or not targetPos then
		return
	end

	local deltaTime = 0.3	-- 默认飞行时间
	local easeType = DT.Ease.Unset	-- 默认速度曲线
	local delayTime = 0
	if params then
		deltaTime = params.time or deltaTime
		easeType = params.easeType or easeType
		delayTime = params.delay or delayTime
	end

	local t = bee.tween(obj, true)
	:to(deltaTime, {position = targetPos})
	:ease(easeType)
	:delay(delayTime)
	:onComplete(function()
		if params and params.isShowTargetEft then
			self:showTargetEft(targetPos)
		end
		if callback then
			callback()
		end
	end)
	:link()

	return t
end

-- 曲线飞行
--[[ params =
{
	startPos = 开始位置（世界坐标）
	centerPos = 中间位置（世界坐标）
	time = 动画时间
	isShowTargetEft = 是否播放到达特效
	delay = 延迟时间
}
--]]
function P:playBezierFlight(obj, targetPos, callback, params)
	if bee.isNull(obj) or not targetPos then
		return
	end
	local startPos = obj.transform.position
	local deltaTime = 0.3
	local delay = 0
	if params then
		startPos = params.startPos or startPos
		deltaTime = params.time or deltaTime
		delay = params.delay or 0
	end

	local centerPos
	if params and params.centerPos then
		centerPos = params.centerPos
	else
		centerPos = bee.v3(targetPos.x + 1, targetPos.y - 2, 0)
	end

	local cmp = CS.BezierAction.BezierTo(obj, startPos, centerPos, targetPos, deltaTime)
	cmp.isLocal = false
	cmp.delay = delay
	cmp:OnComplete(function()
		if params and params.isShowTargetEft then
			self:showTargetEft(targetPos)
		end
		if callback then
			callback()
		end
	end)

	return cmp
end

-- 后撤步飞行动画（先往反方向移动一定距离后再飞向目标点）
-- 曲线飞行
--[[ params =
{
	startPos = 开始位置（世界坐标）
	time = 动画时间
	delay = 延迟播放
	isShowTargetEft = 是否播放到达特效
	backDis = 反方向移动距离
	centerCallback = 反方向移动后的回调
}
--]]
function P:playDropStepFlight(obj, targetPos, callback, params)
	if params and params.startPos then
		obj.transform.position = params.startPos
	end

	local backDis = 0.5
	if params and params.backDis then
		backDis = params.backDis
	end
	local x, y = self:getNegativeDirectionPos(obj.transform.position, targetPos, backDis)
	local centerPos = bee.v3(x, y, 0)

	local deltaTime = 0.7	-- 默认飞行时间
	local delayTime = 0
	if params then
		deltaTime = params.time or deltaTime
		delayTime = params.delay or delayTime
	end

	local t = bee.tween(obj, true)
	:to(deltaTime * 0.44, {position = centerPos})
	:ease(DT.Ease.Linear)
	:onComplete(function()
		if params and params.centerCallback then
			params.centerCallback()
		end
		bee.tween(obj, true)
		:to(deltaTime * 0.56, {position = targetPos})
		:ease(DT.Ease.InQuad)
		:onComplete(function()
			if params and params.isShowTargetEft then
				self:showTargetEft(targetPos)
			end
			if callback then
				callback()
			end
		end)
		:link()
	end)
	:link()

	return t
end

-- 缩放动画
--[[ params =
{
	time = 动画时间
	ease = 缓动效果
	delay = 延迟时间
}
--]]
function P:playZoomAnim(obj, zoomScale, callback, params)
	if bee.isNull(obj) or not zoomScale then
		return
	end

	local easeType = DT.Ease.Unset	-- 默认速度曲线
	local deltaTime = 0.15
	local delayTime = 0
	if params then
		easeType = params.easeType or easeType
		deltaTime = params.time or deltaTime
		delayTime = params.delay or delayTime
	end

	local t = bee.tween(obj)
	:to(deltaTime, {scale = zoomScale})
	:ease(easeType)
	:delay(delayTime)
	:onComplete(function()
		if callback then
			callback()
		end
	end)
	:link()
end

-- 回弹效果
--[[ params =
{
	time1 = 动画时间1
	time2 = 动画时间2
	smallScale = 缩小尺寸
	bigScale = 放大尺寸
	endScale = 最终尺寸
	delay = 延迟时间
}
--]]
function P:playBounceAnim(obj, callback, params)
	if bee.isNull(obj) then
		return
	end

	local curScale = obj.transform.localScale.x
	local bigScale = curScale + 0.1
	local smallScale = curScale + 0.05
	local endScale = curScale
	local deltaTime1 = 0.05
	local deltaTime2 = 0.1
	local delayTime = 0
	if params then
		smallScale = params.smallScale or smallScale
		bigScale = params.bigScale or bigScale
		endScale = params.endScale or endScale
		deltaTime1 = params.time1 or deltaTime1
		deltaTime2 = params.time2 or deltaTime2
		delayTime = params.delay or delayTime
	end

	local t = bee.tween(obj)
	:delay(delayTime)
	:to(deltaTime1, {scale = bigScale})
	:to(deltaTime1, {scale = endScale})
	:to(deltaTime2, {scale = smallScale})
	:to(deltaTime2, {scale = endScale})
	:onComplete(function()
		if callback then
			callback()
		end
	end)
	:link()

	return t
end

-- 放大并带回弹效果动画
--[[ params =
{
	time = 总时长
	smallScale = 缩小尺寸
	bigScale = 放大尺寸
}
--]]
function P:playZoomWithBounce(obj, zoomScale, callback, params)
	if bee.isNull(obj) or not zoomScale then
		return
	end

	local bigScale = zoomScale + 0.1
	local smallScale = zoomScale + 0.05
	local deltaTime = 0.5
	if params then
		smallScale = params.smallScale or smallScale
		bigScale = params.bigScale or bigScale
		deltaTime = params.time or deltaTime
	end

	local time1 = deltaTime * 0.2
	local time2 = deltaTime * 0.34

	local t = bee.tween(obj)
	:to(deltaTime * 0.3, {scale = bigScale})
	:to(deltaTime * 0.2, {scale = zoomScale})
	:to(deltaTime * 0.25, {scale = smallScale})
	:to(deltaTime * 0.25, {scale = zoomScale})
	:ease(DT.Ease.OutQuad)
	:onComplete(function()
		if callback then
			callback()
		end
	end)
	:link()
end

function P:playFloatUpAnim(obj, callback)
	bee.tween(obj)
	:to(0.2, {scale = 1})
	:ease(CS.DG.Tweening.Ease.OutBounce)
	:onComplete(function ()
		bee.once(0.2, function()
			local pos = obj.transform.position
			bee.tween(obj, true)
			:to(0.7, {position = bee.v3(pos.x, pos.y + 1, pos.z)})
			:onComplete(function ()
				if callback then
					callback()
				end
			end)
			:link()
			bee.once(0.4, function()
				bee.tween(obj, true)
				:to(0.3, {alpha = 0})
				:link()
			end, obj)
		end, obj)
	end)
	:link()
end


-- 放大抖动效果
--[[ params =
{

}
--]]
function P:playZoomWithShake(obj, params, callback)
	local delayTime = 1
	local bigTime = 0.2
	local bigScale = 1.2
	local shakeDt = 0.1
	local shakeValue = 2
	local smallTime = 0.2
	local smallScale = 1
	local baseAngle = 0
	if params then
		delayTime = params.delayTime or delayTime
		bigTime = params.bigTime or bigTime
		bigScale = params.bigScale or bigScale
		shakeDt = params.shakeDt or shakeDt
		shakeValue = params.shakeValue or shakeValue
		smallTime = params.smallTime or smallTime
		smallScale = params.smallScale or smallScale
		baseAngle = params.baseAngle or baseAngle
	end
	bee.tween(obj)
    :delay(delayTime)
	:to(bigTime, {scale = bigScale})
	: to(shakeDt, {rotate = bee.v3(0, 0, baseAngle - shakeValue)})
	: to(shakeDt, {rotate = bee.v3(0, 0, baseAngle + shakeValue)})
	: to(shakeDt, {rotate = bee.v3(0, 0, baseAngle - shakeValue)})
	: to(shakeDt, {rotate = bee.v3(0, 0, baseAngle + shakeValue)})
	: to(shakeDt, {rotate = bee.v3(0, 0, baseAngle - shakeValue)})
	: to(shakeDt, {rotate = bee.v3(0, 0, baseAngle)})
	:to(smallTime, {scale = smallScale})
	:onComplete(function()
		if callback then
			callback()
		end
	end)
	:link()
end

return AnimationMgr