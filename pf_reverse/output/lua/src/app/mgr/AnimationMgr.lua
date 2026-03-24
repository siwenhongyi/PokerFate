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
			if animator ~= nil and callback ~= nil then
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
	local eft = ObjectCache:getItemWithName(name)
	if eft then
		if layer then
			eft.gameObject.layer=layer
			CS.Utils.SetAllChildLayer(eft.transform,layer)
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

function P:showEffect(name, to, parent, dt, scale)
	local effectObj = bee.createObj(name)
	if bee.isNull(effectObj) then
		return
	end
	if parent then
		effectObj.transform:SetParent(parent.transform, false)
		effectObj.transform.localPosition = to
	else
		if bee.isNull(self._Canvas) then return nil end
		effectObj.transform:SetParent(self._Canvas.transform, false)
		effectObj.transform.position = to
	end
	if scale then
		effectObj.transform.localScale = bee.v3(scale, scale, scale)
	end
	if -1 ~= dt then
		CU.GameObject.Destroy(effectObj, dt or 2)
	end

	return effectObj
end

function P:PlayAllParticle(rootObj)
	CS.AnimatorManager.Instance:PlayAllChildParticle(rootObj)
end

function P:StopAllParticle(rootObj)
	CS.AnimatorManager.Instance:StopAllChildParticle(rootObj)
end

function P:getAnimRoot(params)
	local ui = UiManager:showUI("MainUIAnim", params)
	return ui
end

function P:getPropTargetPos(prop)
	local posData = tpl_props[prop.id].flutter
	local targetPos = bee.v3(0, 0, 0)	
	
	if not posData then
		printError(" 道具Id " .. prop.id .. "策划未配置飞行位置")
		return 
	end	

	return self:getTargetPos(posData[1], posData[2])
end

function P:getTargetPos(posType, child)
	if not self._PropsFlutteRoot then
		return
	end
	
	local flyParent = self._PropsFlutteRoot[posType]
	if bee.isNull(flyParent) then
		return
	end
	
	local targetTrans = flyParent.transform:Find(FlutterListsChild[posType][child])
	return targetTrans.position
end

-- 获取设置按钮位置
function P:getSettingBtnPos()
	if not self._lobbyMenuIconList then
		return
	end
	
	local targetTrans = self._lobbyMenuIconList[5].transform
	return targetTrans.position
end

-- 获取道具飞行终点Object
function P:getPropTargetObj(prop)
	local cfg = tpl_props[prop.id]
	if not cfg then
		return
	end

	if LobbyUIObj[cfg.propType] then
		local parentTrans = self._PropsFlutteRoot[LobbyUIObj[cfg.propType].parent]
		local childPath = LobbyUIObj[cfg.propType].child
		if parentTrans then
			return parentTrans:Find(childPath).gameObject
		end
	end
end

-- 主界面道具飞行起始位置
function P:getLobbyUIPropFromPos()
	return bee.v3(0, -500, 0)
end

-- 获取反方向移动位置
-- distance为斜边距离
function P:getNegativeDirectionPos(fromPos, toPos, moveDis)
	local x = math.abs(toPos.x - fromPos.x)
	local y = math.abs(toPos.y - fromPos.y)
	local distance = math.sqrt(math.pow((x), 2) + math.pow((y), 2))
	
	local x1, y1 = 0, 0
	if distance > 0 then
		x1 = x * moveDis / distance
		y1 = y * moveDis / distance
	end

	local x2 = fromPos.x + ((fromPos.x - toPos.x) < 0 and -1 or 1) * x1
	local y2 = fromPos.y + ((fromPos.y - toPos.y) < 0 and -1 or 1) * y1

	return x2, y2
end

-- ============================ 通用特效显示 ============================

-- 显示目标落点粒子特效
function P:showTargetEft(to, parent, dt, layer)
	local eft = self:showEffect("New_effect/Prefab/eff_ui_ItemSlot_one_light01", to, parent, dt)
	if eft then
		eft.transform:SetAsFirstSibling()
		local sortingLayer = layer or 6
		if parent then
			local canvas = parent:GetComponent(typeof(CU.Canvas))
			if not bee.isNull(canvas) then
				sortingLayer = sortingLayer + canvas.sortingOrder
			end
		end
		bee.setSortingOrder(eft, sortingLayer)
	end
	return eft
end

function P:showTargetEftBig(to, parent, dt, scale)
	return self:showEffect("New_effect/Prefab/eff_ui_ItemSlot_one_light02", to, parent, dt, scale)
end

-- ============================ 通用动画 ============================

-- 主界面飞道具（包括金币）
function P:mainUIFlyProps(propLists, callback)
	printError("方法已废弃")
	if callback then
		callback()
	end
end

-- 过关后获得奖励动画
function P:playLevelRewardAnim(rewardList, callback)
	if not rewardList or #rewardList == 0 then
		if callback then callback() end
		return
	end

	local goldCount = 0
	local starCount = 0

	for k,v in pairs(rewardList) do
		if v.id == GPropId.Gold then
			goldCount = v.count
		elseif v.id == GPropId.Star then
			starCount = v.count
		end
	end

	local flyGoldDelayTime = 0
	
	if starCount > 0 then
		self:playFlyStarAnim(starCount)
		flyGoldDelayTime = 0.3
	end

	local s = bee.once(flyGoldDelayTime, function()
		self:playFlyGoldAnim(goldCount, function()
			if callback then
				callback()
			end
		end)
	end)
	
	return s
end

-- 主界面飞金币动画
function P:playFlyGoldAnim(goldCount, callback, fromPos, toPos, flyCallback, dt, skipBounce)
	Game:playSound("gold_display")

	local goldPropInfo = {id = GPropId.Gold, count = goldCount}
	if not fromPos then
		fromPos = self:getLobbyUIPropFromPos()
	end
	if not toPos then
		toPos = self:getPropTargetPos(goldPropInfo)
	end

	local effectGoldObjList = {}

	local flyCount = 10	--动画金币个数
	local perCount = math.floor(goldCount / flyCount)
	local parent = self:getAnimRoot({props = goldPropInfo})

	-- 生成金币
	for i = 1, flyCount do
		-- local objIndex = math.random(1, 2)
		local path = "New_effect/Prefab/eff_ingame_1341_jingbi"
		-- if objIndex ~= 1 then
		-- 	path = path .. objIndex
		-- end

		local effectGold = ResManager:GetGameObject(path)		
		local ranPos = CU.Random.insideUnitCircle * 65
		effectGold.transform:SetParent(parent.transform, false)
		effectGold.transform.localPosition = bee.v3(fromPos.x + ranPos.x, fromPos.y + ranPos.y, 0)
		effectGold.transform.localScale = bee.v3(1, 1, 1)

		bee.refreshSortingOrder(effectGold)

		effectGold:SetActive(false)
		table.insert(effectGoldObjList, effectGold)
	end

	-- 金币显示
	for i = 1, flyCount do
		-- 飞行动画
		parent:once((i - 1) * 0.06, function()
			effectGoldObjList[i]:SetActive(true)
		end)
	end

	-- 金币飞行
	parent:once(flyCount * 0.06, function()
		local index = 0
		for i = flyCount, 1, -1 do
			local perAddCount = 0
			if i < flyCount then
				perAddCount = perCount
			else
				perAddCount = goldCount - (flyCount - 1) * perCount
			end
			local effectGold = effectGoldObjList[i]
			local itemPos = effectGold.transform.position
			self:playBezierFlight(effectGold, toPos, function()
				Game:playSound("gold_hit")
				if flyCallback then
					flyCallback(perAddCount)
				else
					ItemModel:addShowDataVal(GPropType.Gold, perAddCount)
				end
				if not skipBounce then
					self:playPropTargetBounce(goldPropInfo)
				end
				
				index = index + 1
				if index == flyCount then
					CU.GameObject.DestroyImmediate(parent.node)
					if callback then
						callback()
					end
				end
				CU.GameObject.Destroy(effectGold)
			end, {time = dt or 0.7, delay = (i - 1) * 0.06, centerPos = bee.v3(itemPos.x - 2, itemPos.y - 1.5, itemPos.z), isShowTargetEft = true})
		end
	end)

	self:playFlyGoldNumAnim(goldCount, parent, fromPos)
end

-- 金币数量动画
function P:playFlyGoldNumAnim(goldCount, parent, fromPos)
	local numItem = ResManager:GetGameObject("views/ItemPrefab/FlyGoldNumItem")
	numItem.transform:SetParent(parent.transform, false)
	numItem.transform.localPosition = fromPos
	numItem.transform.localScale = bee.v3(1, 1, 1)

	bee.refreshSortingOrder(numItem)
	bee.setText(numItem.transform:Find("NumText"), "+" .. goldCount)

	bee.setAlpha(numItem, 0)
	bee.tween(numItem)
	:to(0.4, {alpha = 1})
	:delay(0.6)
	:toFloat(1, 0, 0.5, function(v)
		bee.setAlpha(numItem, v)
	end)
	:link()

	local curPos = numItem.transform.position
	self:playStraightFlight(numItem, bee.v3(curPos.x, curPos.y + 1, curPos.z), function()
		CU.GameObject.Destroy(numItem)
	end, {time = 1.5})

end

-- 主界面飞星星动画
function P:playFlyStarAnim(starCount, callback)
	Game:playSound("star_display")

	local propInfo = {id = GPropId.Star, count = 1}
	if not fromPos then
		fromPos = self:getLobbyUIPropFromPos()
	end
	if not toPos then
		toPos = self:getPropTargetPos(propInfo)
	end

	local starObjList = {}

	local flyCount = starCount	--动画金币个数
	local perCount = math.floor(starCount / flyCount)
	local parent = self:getAnimRoot({props = propInfo})

	self:playUIEffect("New_effect/Prefab/eff_ui_ItemSlot_one_light01", parent.transform, fromPos)

	local index = 0
	for i = 1, flyCount do
		local starObj = ResManager:GetGameObject("New_effect/InGameEftBase/eff_ingame_icon_star")
		starObj.transform:SetParent(parent.transform, false)
		starObj.transform.localPosition = fromPos
		starObj.transform.localScale = bee.v3(1, 1, 1)
		starObj:SetActive(true)
		bee.refreshSortingOrder(starObj)

		local ranPos = CU.Random.insideUnitCircle * 2
		local centerPos = bee.v3(starObj.transform.position.x + ranPos.x, starObj.transform.position.y + ranPos.y, starObj.transform.position.z)
		local deltaTime = 0.8 + math.random() * 0.2

		local perAddCount = 0
		if i < flyCount then
			perAddCount = perCount
		else
			perAddCount = starCount - (flyCount - 1) * perCount
		end
		
		AnimationMgr:playBezierFlight(starObj, toPos, function()
			Game:playSound("star_hit")
			ItemModel:addShowDataVal(GPropType.Star, perAddCount)
			self:playPropTargetBounce(propInfo)
			
			index = index + 1
			if index == flyCount then
				CU.GameObject.DestroyImmediate(parent.node)
				if callback then
					callback()
				end
			end

			CU.GameObject.Destroy(starObj)
		end, {centerPos = centerPos, time = deltaTime, isShowTargetEft = true})
	end
end

-- 向上飘的奖励动画
function P:SkyUpRewardAnim(propsList, target, finishedCb, notDelay, yPosOffset)
	if not target then
		return
	end
	local setRewards = {}
	for k, v in pairs(propsList) do
		if tpl_props[v.id].propType == GPropType.Gift then --礼包
			local giftInfo = bee.getGiftProps(v)
			table.addRange(setRewards, giftInfo)
		else
			table.insert(setRewards, v)
		end
	end
	local propCount = #setRewards
	local popCanvas = UiManager:getPopRoot()
	local fromPos = CS.Utils.UtilsWorldToScreenPointToWorld(popCanvas, target.gameObject)

	local xOffset = 0
	if propCount >= 2 then
		local xRight = fromPos.x + 60 + 77
		local sceneWidth = CU.Screen.width
		if xRight > sceneWidth then
			xOffset = sceneWidth - xRight
		end

		local xLeft = fromPos.x - 60 - 77
		if xRight < 0 then
			xOffset = xLeft
		end
	end

	for i = 1, propCount do
		bee.once(i * 0.27, function()
			local scaleTime = 0.14
			local itemPos
			if propCount == 1 then
				scaleTime = 0.33
				itemPos = bee.v3(fromPos.x, fromPos.y + (yPosOffset or 100), fromPos.z)
			else
				local x = (i - 1) % 2
				local y = math.floor((i - 1) / 2)

				local startPos = bee.v3(fromPos.x + xOffset, fromPos.y + (yPosOffset or 200), fromPos.z)
				--itemPos = bee.v3(startPos.x - 60 + x * 120, startPos.y + 40 - y * 80, startPos.z)
				itemPos = bee.v3(startPos.x - 60 + x * 120, startPos.y + (i - 1) * 40 - y * 70, startPos.z)
			end
			local propItemObj = ResManager:GetGameObject("views/ItemPrefab/ItemSlot")
			propItemObj.name = "SkyUpRewardItem" .. i
			propItemObj.transform:SetParent(popCanvas.transform, true)
			propItemObj.transform.position = itemPos
			propItemObj.transform.localScale = bee.v3(1, 1, 1)
			bee.emitTo(propItemObj, "init", setRewards[i], {receive = true})
			-- bee.emitTo(propItemObj, "showAddText")

			Game:playSound("reward_display2")

			bee.once(scaleTime - 0.4, function()
				local eft = AnimationMgr:playUIEffect("New_effect/UIEft/eff_ui_libao_daoju_zhanshi01", propItemObj.transform, bee.v3())
				eft.transform:SetAsFirstSibling()
			    CS.AnimatorManager.AddUIParticle(eft, 0.8)

			    -- local eff = propItemObj.transform:Find("Eft")
				-- if eff and not bee.isNull(eff) then
				-- 	eff.gameObject:SetActive(true)
				-- end
			end)
			-- bee.tween(propItemObj)
			-- :to(scaleTime, {scale = 0.7})
			-- :ease(CS.DG.Tweening.Ease.OutBounce)
			-- :onComplete(function ()
				bee.tween(propItemObj)
				: by(0.73, {y = 160}, false)
				:link()
				bee.once(0.46, function()
					bee.tween(propItemObj)
					: to(0.37, {alpha = 0})
					:onComplete(function ()
						CU.GameObject.Destroy(propItemObj)
						if propCount == i and finishedCb then
							finishedCb()
						end
					end)
					:link()
				end)
			-- end)
			-- :link()
		end)
	end
end

-- 主界面出现道具飞道具动画（购买成功动画显示）
function P:playLobbyRewardPropAnim(propsList, finishCallback)
	local goldCount = 0
	local rewardList = {}
	for k,v in pairs(propsList) do
		if v.id == GPropId.Gold then
			goldCount = goldCount + v.count
		else
			v.ShowPriority = tpl_props[v.id].ShowPriority
			table.insert(rewardList, v)
		end
	end
	table.sort(rewardList, function(a, b) return a.ShowPriority > b.ShowPriority end)

	local startPos = self:getLobbyUIPropFromPos()
	if goldCount > 0 then
		self:playFlyGoldAnim(goldCount, function()
			self:playLobbyFlyPropAnim(rewardList, finishCallback)
		end)
	else
		self:playLobbyFlyPropAnim(rewardList, finishCallback)
	end
end

function P:playLobbyFlyPropAnim(rewardList, finishCallback)
	if not rewardList or not next(rewardList) then
		if finishCallback then
			finishCallback()
		end
		if bee.existTask() then
			bee.runNextTask()
		end
		return
	end

	local fromPos = self:getLobbyUIPropFromPos()
	local parent = self:getAnimRoot({props = rewardList})

	-- 偏移参数
	local y = 200
	local x = 50

	-- 生成并设定位置
	local itemList = {}
	for i, v in ipairs(rewardList) do
		local index1 = math.ceil(i / 3)
		local index2 = i % 3

		local item = ResManager:GetGameObject("views/ItemPrefab/ItemSlot")
		bee.emitTo(item, "init", v)

		local xDelta
		local yDelta
		if index2 == 0 then
			xDelta = 100
			yDelta = index1 * y + y / 2
		elseif index2 == 1 then
			xDelta = 0
			yDelta = index1 * y
		elseif index2 == 2 then
			xDelta = -100
			yDelta = index1 * y + y / 2
		end

		item.transform:SetParent(parent.transform)
		item.transform.localPosition = bee.v3(fromPos.x + xDelta, fromPos.y + yDelta, fromPos.z)
		item.transform.localScale = bee.v3(0, 0, 0)

		table.insert(itemList, {item = item, data = v})
	end
	
	-- 出现动画
	for i, v in ipairs(itemList) do
		parent:once(i * 0.1, function()
			self:playZoomWithBounce(v.item, 1.3, nil, {bigScale = 1.7})
		end)
	end

	-- 飞道具动画
	local itemCount = #itemList
	parent:once(itemCount * 0.1, function()
		local index = 0
		for i, v in ipairs(itemList) do
			parent:once(i * 0.2, function()
				local targetPos = self:getPropTargetPos(v.data)
				self:playDropStepFlight(v.item, targetPos, function()
					Game:playSound("reward_hit")
					CU.GameObject.Destroy(v.item)

					local cfg = tpl_props[v.data.id]
					self:playPropTargetBounce(cfg)
					-- 道具飞行动画后刷新主界面的道具显示
					for propType, propId in pairs(ItemModel.ShowValuePropType) do
						if cfg.propType == propType then
							if cfg.duration and cfg.duration > 0 then
								ItemModel:addShowDataVal(cfg.propType, nil, v.data.count * cfg.duration)
							else
								ItemModel:addShowDataVal(cfg.propType, v.data.count)
							end
						end
					end

					index = index + 1
					if index == itemCount then
						CU.GameObject.DestroyImmediate(parent.node)
						if finishCallback then
							finishCallback()
						end
						if bee.existTask() then
							bee.runNextTask()
						end
					end
				end)
			end)
		end
	end)
end

-- 所有道具图标
function P:FlyActivityItems(datas)
	local parent = self:getAnimRoot({actives = datas})
	local dt = 0
	for k, v in ipairs(datas) do
		dt = k * tpl_constdata.ActivityPropEffectInterval / 1000
		parent:once(dt, function()
			bee.emit("evt_onFlyActItem", v.activeData)
			self:FlyActivityItem(v.activeData, v.act.val, v.act.multiple, function()
				if k == #datas then
					CU.GameObject.DestroyImmediate(parent.node)
					bee.runNextTask()  --飞积分后播放后续任务队列(如果有)
				end
			end, parent)
		end)
	end
end

-- 活动道具图标
function P:FlyActivityItem(activityData, count, multiple, finishCallback, parent)
	bee.emit("evt_FlyActivityItem", activityData.activityId)
	local ActivityItem = bee.createObj("views/ItemPrefab/FlyActivityItem")
	local FlyIcon = ActivityItem.transform:Find("FlyIcon")
	FlyIcon.gameObject:SetActive(false)

	local targetPos = activityData.itemObj.transform.position
	ActivityItem.transform:SetParent(parent.transform, false)
	local offsetX
	if activityData.column == 2 then
		offsetX = -0.7
	else
		offsetX = 0.7
	end
	ActivityItem.transform.position = bee.v3(targetPos.x + offsetX, targetPos.y, targetPos.z)
	bee.setSortingOrder(ActivityItem, 6)

	local flyCount = math.min(count, tpl_constdata.ActivityItemShowNum)
	if activityData.activityId == ActivityID.ColorBall then
		flyCount = 1
	end

	-- 生成活动图标
	local flyIconList = {}
	for i = 1, flyCount do
		Game:playSound("activityPoints_get")
		local copyIcon = CU.GameObject.Instantiate(FlyIcon.gameObject)
		local Icon = copyIcon.transform:Find("Icon")
		local iconPath = activityData.activityPic
		if activityData.activityId == ActivityID.SkyCastle then
			iconPath = SkyCastleModel:getActivityPic()
		end
		bee.setIcon(Icon, iconPath)

		local ranPos = CU.Random.insideUnitCircle * 30
		copyIcon.transform:SetParent(ActivityItem.transform)
		copyIcon.transform.localPosition = bee.v3(ranPos.x, ranPos.y, 0)
		copyIcon.transform.localScale = bee.v3(1, 1, 1)
		copyIcon.gameObject:SetActive(true)
		table.insert(flyIconList, 1, copyIcon)
	end

	for i = 1, flyCount do
		local flyIcon = flyIconList[i]
		bee.setAlpha(flyIcon, 0)
		-- flyIcon.transform.localScale = bee.v3(0, 0, 0)
		parent:once(0.25 * (i - 1), function()
			flyIcon.gameObject:SetActive(true)
			bee.tween(flyIcon)
			:to(0.35, {alpha = 1})
			:onComplete(function()
				local IconAnimator = flyIcon.transform:Find("Icon"):GetComponent("Animator")
				self:playBounceAnim(flyIcon, nil, {bigScale = bee.v3(1, 1.2, 1)})
			end)
			:link()
		end)
	end
	local iconAnimTime = 0.1 * flyCount
	local iconFlyEndTime = 0.2 * (flyCount + 1) + 0.2
	-- 数字
	local NumItem
	if activityData.column == 2 then
		NumItem = ActivityItem.transform:Find("LeftNumItem")
	else
		NumItem = ActivityItem.transform:Find("RightNumItem")
	end
	bee.setAlpha(NumItem, 0)
	NumItem.gameObject:SetActive(true)

	-- 数字上升动画
	local NumFloatAnimFunc = function()
		self:playBounceAnim(NumItem, function()
			bee.tween(NumItem)
			:to(1, {y = 100})
			:link()
			bee.tween(NumItem)
			:toFloat(1, 0, 0.5, function(v)
				bee.setAlpha(NumItem, v)
			end, {delay = 0.05, bigScale = 1.2})
			:link()
		end)
	end
	local numFlyEndTime = 1.9

	local numAnimTime
	if multiple and multiple > 1 then
		-- 倍数动画
		local NormalNum = NumItem.transform:Find("NormalNum")
		local AddNum = NumItem.transform:Find("AddNum")
		local MultipleIcon = NumItem.transform:Find("MultipleIcon")
		bee.setText(NormalNum, "+" .. count)
		bee.setText(AddNum, "+" .. count * multiple)
		AddNum.gameObject:SetActive(false)
		MultipleIcon.gameObject:SetActive(true)
		bee.tween(NumItem)
		:to(0.5, {alpha = 1})
		:onComplete(function()
			MultipleIcon.gameObject:SetActive(true)

			local startPos = MultipleIcon.transform.position
			local targetPos = NormalNum.transform.position
			local centerPos = bee.v3((startPos.x + targetPos.x) / 2, startPos.y)
			self:playBezierFlight(MultipleIcon.gameObject, targetPos, function()
				AddNum.gameObject:SetActive(true)
				NormalNum.gameObject:SetActive(false)
				MultipleIcon.gameObject:SetActive(false)
				self:showTargetEft(AddNum.transform.position, parent.transform)
				bee.emit("evt_flyActivityItemEnd", activityData)
			end, {centerPos = centerPos, isShowTargetEft = true})
		end)
		:link()
		numAnimTime = 0.7
	else
		local NormalNum = NumItem.transform:Find("NormalNum")
		local AddNum = NumItem.transform:Find("AddNum")
		local MultipleIcon = NumItem.transform:Find("MultipleIcon")
		bee.setText(NormalNum, "+" .. count)
		AddNum.gameObject:SetActive(false)
		MultipleIcon.gameObject:SetActive(false)

		bee.tween(NumItem)
		:to(0.5, {alpha = 1})
		:link()
		numAnimTime = 0.5
	end

	-- 活动图标动画(出现->跳入活动图标)
	local ActivityIconAnimFunc = function()
		for i = 1, flyCount do
			local copyIcon = flyIconList[i]
			parent:once(i * 0.25, function()
				local startPos = copyIcon.transform.position
				local centerPos = bee.v3((startPos.x + targetPos.x) / 2, startPos.y + 1.2)
				self:playBezierFlight(copyIcon, targetPos, function()
					Game:playSound("activityPoints_hit")
					copyIcon.gameObject:SetActive(false)
					--
					activityData.itemObj.transform.localScale = bee.v3(1,1,1)
					self:playBounceAnim(activityData.itemObj, nil, {bigScale = bee.v3(1, 1.2, 1)})
					
					--
				end, {centerPos = centerPos, isShowTargetEft = i == flyCount, time = 0.25})
			end)
		end
	end

	parent:once(math.max(iconAnimTime, numAnimTime), function()
		ActivityIconAnimFunc()
		NumFloatAnimFunc()
		bee.emit("evt_flyActivityItemEnd", activityData)
		-- 播放结束后移除动画item
		parent:once(math.max(numFlyEndTime, iconFlyEndTime), function()
			CU.GameObject.Destroy(ActivityItem)
			if finishCallback then
				finishCallback()
			end
		end)
	end)
end

-- 播放道具飞行到达后的缩放动画
function P:playPropTargetBounce(prop)
	local targetObj = self:getPropTargetObj(prop)
	if not targetObj then
		return
	end

	if not self.targetObjBounceTweenList then
		self.targetObjBounceTweenList = {}
	end

	if self.targetObjBounceTweenList[targetObj.name] then
		self.targetObjBounceTweenList[targetObj.name]:kill()
		self.targetObjBounceTweenList[targetObj.name] = nil
	end
	
	targetObj.transform.localScale = bee.v3(1, 1, 1)
	
	self.targetObjBounceTweenList[targetObj.name] = self:playBounceAnim(targetObj)
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

