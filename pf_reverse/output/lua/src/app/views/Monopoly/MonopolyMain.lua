local P = class("MonopolyMain", UiFullView)

function P:onAwake()
    local AnimRoot = self:find("AnimRoot")
    self.Center = self:find("Center", AnimRoot)
    self.RightTop = self:find("RightTop", AnimRoot)
    self.RightBottom = self:find("RightBottom", AnimRoot)
    self.Top = self:find("Top", AnimRoot)
    self.LeftTop = self:find("LeftTop", AnimRoot)

    self.LeftTopGlass = self:find("LeftTopGlass", AnimRoot)
    self.RightTopGlass = self:find("RightTopGlass", AnimRoot)

    self.ProgressRoot = self:find("Progress", self.Center)
    self.ProgressPoints = self:find("PointValue", self.ProgressRoot)
    self.Progress = self:find("Progress", self.ProgressRoot)
    self.CurProgressValue = self:find("Value", self.ProgressRoot)
    self.Items = self:find("Items", self.ProgressRoot)
    self.RoadMap = self:find("RoadMap", self.Center)
    self.RoadPoint = self:find("RoadPoint", self.Center)
    self.Character = self:find("Character", self.Center)
    self.RoleRoot = self:find("Character/Root", self.Center)
    self.Role = self:find("Image", self.RoleRoot)
    self.RoleGetTip = self:find("RewardTip", self.RoleRoot)
    self.RoleGetTipIcon = self:find("ItemIcon/Image", self.RoleGetTip)
    self.RoleGetTipValue = self:find("Value", self.RoleGetTip)
    self.RoleGetFx = self:find("Eff_poker_Ui_Monopoly_zj", self.RoleRoot)
    self.RoleAni = self.RoleRoot:GetComponent("Animator")
    self.Character:SetActive(false)
    self.RoleGetTip:SetActive(false)

    self.Time = self:find("Time/text", self.RightTop)
    self.cutDownTag = nil

    self.TaskButton = self:find("TaskButton", self.RightBottom)
    self.GoButton = self:find("GoButton", self.RightBottom)
    self.AmountValue = self:find("Amount/value", self.RightBottom)
    self.MultipleButton = self:find("MultipleButton", self.RightBottom)
    self.MultipleText = self:find("value", self.MultipleButton)
    self.NumTips = self:find("NumTips", self.RightBottom)
    self.MultipleButtonAni = self.MultipleButton:GetComponent("Animator")

    self.dice = self:find("Dice", self.GoButton)
    self.diceAni = self.dice:GetComponent("Animator")
    self.diceAni.enabled = false
    self.diceTarget = self:find("Target", self.dice)

    self.InfoButton = self:find("InfoButton", self.LeftTop)
    self.BackButton = self:find("BackButton", self.LeftTop)

    self.RoadList = {}
    self.curPos = 1
    self.changeAngle = {{9, -1}, {21, 1}}
    self.roadCount = self.RoadPoint.transform.childCount
    self.MapObject = nil
    self.MapLightFrame = nil
    self.MapRewardItem = self:find("RoadReward", self.Center)
    self.MapRewardItem:SetActive(false)
    self.MapRewardCfg = nil
    self.MapRewardItems = {}
    self.MapDownTime = 0.02

    self.RewardCfgList = {}
    self.RewardItemList = {}

    bee.addClick(self.GoButton, function ()
        -- Game:playSound("ui_button_confirm")
        self:getStepsEvent()
    end)
    bee.addClick(self.MultipleButton, function ()
        Game:playSound("ui_button_confirm")
        self:exchangeMultip()
    end)

    bee.addClick(self.TaskButton, function ()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("MonopolyTask")
        bee.logEvent("monopoly-task")
    end)

    bee.addClick(self.InfoButton, function ()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonRules", {text = _T("LAB_MONOPOLY_ACTIVITY1_RULES_1")})
        bee.logEvent("monopoly-rule")
    end)
    bee.addClick(self.BackButton, function ()
        Game:playSound("ui_button_confirm")
        self:onBtClose()
    end)

    RedManager:bind(self:find("Reddot", self.TaskButton), RedTag.MonopolyTask)

    TaskModel:reportTask(TaskType.CheckView, 19005)
end

function P:onAdapt()
    P.super.onAdapt(self)
    self:refreshGlassPosition()
end

function P:refreshGlassPosition()
    if self.LeftTopGlass == nil or self.RightTopGlass == nil then
        return
    end

    self.LeftTopGlass.transform.anchoredPosition = bee.v2(-self.node.transform.offsetMin.x, 0)
    self.RightTopGlass.transform.anchoredPosition = bee.v2(-self.node.transform.offsetMax.x, 0)
end

function P:onShow()
    self._isClosing = false
    self._isMoving = false
    self._isRolling = false
    self._pendingItemChangeCheck = false
    MonopolyModel.ctrling = false
    self:refreshGlassPosition()

    self:initMap()
    self:initReward()
    self:refreshMultip()
    self:refreshDiceCount()
    self:refreshProgress()
    self:cutDown()

    self.curPos = MonopolyModel.curPos
    self.RoleRoot.transform.position = self.RoadList[self.curPos].transform.position
    self:checkAngle()
    self:setMapLightFrame()

    self:checkExchangeMultip()

    local inMin = MonopolyModel:switchMultipleBtn()
    self.MultipleButton:SetActive(not inMin)
end

--初始化地图
function P:initMap()
    --地图投影
    if not bee.isNull(self.MapObject) and not bee.isNull(self.MapRenderTexture) then
        return
    end
    self:releaseMap()

    local width, height = 1920, 1080
    self.RoadMap.transform.sizeDelta = bee.v2(width, height)
    self.MapObject = bee.createObj("views/Monopoly/MonopolyMap")
    self.MapLightFrame = self:find("Canvas/Roads/monopoly_farme_pattern_select", self.MapObject)
    self.MapLightFrame:SetActive(false)

    local MapRoads = self:find("Canvas/Roads", self.MapObject)
    for _,v in pairs(tpl_monopoly_grid) do
        if v.index ~= 1 and v.chessboard_id == MonopolyModel.chessboardCfg.chessboard_id then
            local mapRoad = self:find(tostring(v.index) .. "/Icon", MapRoads)
            bee.setIcon(mapRoad, v.quality >= 5 and 
                "Monopoly[monopoly_img_pattern_special]" or "Monopoly[monopoly_img_pattern_normal]")
        end
    end
    local roadNum = MapRoads.transform.childCount
    for i = 1, roadNum do
        local point = self:find(tostring(i), MapRoads)
        if not bee.isNull(point) then
            point.gameObject:SetActive(false)
            self:once(self.MapDownTime * i, function ()
                point.gameObject:SetActive(true)
            end)
        end
    end
    self:once(self.MapDownTime * MonopolyModel.curPos, function()
        self:once(0.2, function()
            self.MapLightFrame:SetActive(true)
        end)
        self.Character:SetActive(true)
    end)

    local cameraNode = self:find("Camera", self.MapObject)
    local camera = cameraNode and cameraNode:GetComponent("Camera")
    local rawImage = self.RoadMap:GetComponent("RawImage")
    if bee.isNull(camera) or bee.isNull(rawImage) then
        self:releaseMap()
        return
    end

    self.MapRenderTexture = CU.RenderTexture(width, height, 24)
    self.MapRenderTexture.filterMode = CU.FilterMode.Bilinear
    camera.clearFlags = CU.CameraClearFlags.SolidColor
    camera.backgroundColor = CU.Color(0, 0, 0, 0)
    camera.targetTexture = self.MapRenderTexture
    rawImage.texture = self.MapRenderTexture

    --具体位置
    self.RoadList = {}
    for i = 1, self.roadCount do
        table.insert(self.RoadList, self:find(tostring(i), self.RoadPoint))
    end

    --地图奖励
    self.MapRewardCfg = {}
    for _,v in pairs(tpl_monopoly_grid) do
        if v.chessboard_id == MonopolyModel.chessboardCfg.chessboard_id then
            self.MapRewardCfg[v.index] = v
        end
    end
    for k,v in pairs(self.MapRewardCfg) do
        if v.rewards then
            self:once(self.MapDownTime * k, function ()
                local item = {}
                item.cfg = v
                item.go = CU.GameObject.Instantiate(self.MapRewardItem)
                local propCfg = tpl_props[v.rewards[1]]
                item.icon = self:find("Icon", item.go)
                bee.setIcon(item.icon, propCfg.icon)
                item.value = self:find("Value", item.go)
                bee.setText(item.value, _N2(v.rewards[2] * MonopolyModel.multiple))
                item.go.transform:SetParent(self.RoadList[v.index].transform, false)
                item.go.transform.localPosition = bee.v3zero
                local pt = self:find("Point", item.go)
                bee.addClick(item.go, function ()
                    Game:playSound("ui_button_confirm")
                    UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(v.rewards[1], true), target = pt})
                end)
                item.go:SetActive(true)
                table.insert(self.MapRewardItems, item)
            end)
        end
    end
end

function P:releaseMap()
    for _, item in ipairs(self.MapRewardItems or {}) do
        if not bee.isNull(item.go) then
            bee.destroy(item.go)
        end
    end
    self.MapRewardItems = {}

    if not bee.isNull(self.RoadMap) then
        local rawImage = self.RoadMap:GetComponent("RawImage")
        if not bee.isNull(rawImage) then
            rawImage.texture = nil
        end
    end

    if not bee.isNull(self.MapObject) then
        local cameraNode = self:find("Camera", self.MapObject)
        local camera = not bee.isNull(cameraNode) and cameraNode:GetComponent("Camera")
        if not bee.isNull(camera) then
            camera.targetTexture = nil
        end
        bee.destroy(self.MapObject)
        self.MapObject = nil
    end

    if not bee.isNull(self.MapRenderTexture) then
        self.MapRenderTexture:Release()
        CU.Object.Destroy(self.MapRenderTexture)
        self.MapRenderTexture = nil
    end

    self.MapLightFrame = nil
    self.MapRewardCfg = nil
    self.RoadList = {}
end

--初始化奖励
function P:initReward()
    local activityId = MonopolyModel:getAcitvityId()
    self.RewardCfgList = get_tpl_subKey(tpl_dice_consumption_rewards_list, "activity", activityId)
    table.sort(self.RewardCfgList, function (a, b) return a.id < b.id end)

    local index = 0
    self.RewardItemList = {}
    for _,v in pairs(self.RewardCfgList) do
        index = index + 1
        local item = {}
        item.go = self:find("Item" .. index, self.Items)
        item.frame = self:find("common_item_grid_s_06", item.go)
        item.icon = self:find("Icon", item.go)
        item.num = self:find("num", item.go)
        item.mask = self:find("monolopy_item_grid_m_mask", item.go)
        item.lock = self:find("icon_lock_0", item.go)
        item.geted = self:find("common_item_checkmark", item.go)
        item.reddot = self:find("reddot", item.go)
        item.cfg = v
        item.getable = false
        bee.addClick(item.go, function ()
            if item.getable then
                MonopolyModel:getProgressReward()
                self:logRewardEvent()
            else
                Game:playSound("ui_button_confirm")
		        UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(v.rewards[1], true), target = item.go})
            end
        end)

        local propCfg = tpl_props[v.rewards[1]]
        bee.setIcon(item.frame, string.format("Common[common_item_grid_s_%02d]", propCfg.quality + 1))
        bee.setIcon(item.icon, propCfg.icon)
        bee.setText(item.num, _N2(v.rewards[2]))
        item.mask:SetActive(false)
        item.lock:SetActive(false)
        item.geted:SetActive(false)
        item.reddot:SetActive(false)

        table.insert(self.RewardItemList, item)

        local proBackPt = self:find("val" .. index, self.ProgressPoints)
        bee.setText(proBackPt, v.quantity)
        local proPt = self:find("val" .. index, self.Progress)
        bee.setText(proPt, v.quantity)
    end
end

function P:logRewardEvent()
    local maxId = 0
    for _,v in pairs(self.RewardItemList) do
        if v.getable and v.cfg.id > maxId then
            maxId = v.cfg.id
        end
    end
    bee.logEvent("monopoly-point-reward", maxId)
end

--投掷色子
function P:getStepsEvent()
    if self._isClosing or self._isMoving or self._isRolling or MonopolyModel.ctrling then
        return
    end

    local costCount = MonopolyModel:getItemCount()
    if costCount <= 0 then
        UiManager:showToast(_F("LAB_SHOP_COMMON_24", _T(tpl_props[MonopolyModel.activityItemId].name)))
        return
    end

    if bee.checkCd("MonopolyPlaying", 1) then
        self._isRolling = true
        MonopolyModel:playEvent()
        bee.logEvent("monopoly-roll", MonopolyModel.multiple)
    end
end

--投掷色子回调
function P:evt_MonopolyPlay(data)
    if self._isClosing then
        return
    end

    self._isRolling = true
    self.diceAni.enabled = true
    local steps = MonopolyModel.curPos - self.curPos
    if steps < 0 then
        steps = steps + #self.RoadList
    end
    bee.setIcon(self.diceTarget, "Icon[icon_10420002_" .. steps .. "]")
    Game:playSound("sound_sugoroku_dice")
    AnimationMgr:play(self.diceAni, "UI_1_Monopoly_touzi", function ()
        if self._isClosing then
            return
        end
        local roadCount = #self.RoadList
        if self._isMoving or roadCount == 0 then
            return
        end
        self._isMoving = true

        self:once(0.2, function()
            self:moveEvent(steps, data.multiple)
            -- self:refreshDiceCount()
            self:refreshProgress()
        end)
    end)

    -- local jumpGears = MonopolyModel:checkJumpGearsMultip()
    -- if jumpGears then
    --     self:refreshMultip()
    -- end
end

--角色移动
function P:moveEvent(steps, multiple)
    local roadCount = #self.RoadList
    local moveTween = bee.tween(self.RoleRoot, true)
    -- local mapLightFrameTween = bee.tween(self.MapLightFrame)
    local plannedPos = self.curPos
    local roleDefaultY = self.Role.transform.localPosition.y
    -- self.MapLightFrame:SetActive(false)
    local mapLightGroup = self.MapLightFrame:GetComponent("CanvasGroup")
    local mapLightTween = bee.tween(self.MapLightFrame):to(0.5, {alpha = 0}):link()
    
    for _ = 1, steps do
        plannedPos = plannedPos % roadCount + 1
        local nextPos = plannedPos
        -- moveTween:to(0.08, {position = self.RoleRoot.transform.position})
        moveTween:call(function()
            if self._isClosing then
                return
            end
            self.RoleAni.enabled = true
            AnimationMgr:playAnimator(self.RoleAni, "UI_1_Monopoly_character_root")
            bee.tween(self.Role)
                :delay(0.15)
                :to(0.15, {y = roleDefaultY + 30})
                :to(0.15, {y = roleDefaultY})
                :ease(DT.Ease.Linear)
                :link()
        end)
        moveTween:delay(0.15)
        moveTween:to(0.3, {position = self.RoadList[nextPos].transform.position})

        -- local point = self:find("Canvas/Roads/" .. nextPos, self.MapObject)
        -- local targetPosition = point.transform.localPosition + bee.v3(-1, 21, 0)
        -- mapLightFrameTween:delay(0.15)
        -- mapLightFrameTween:to(0.3, {position = targetPosition})

        moveTween:call(function()
            if self._isClosing then
                return
            end
            self.curPos = nextPos
            local roadLight = self:find(string.format("Canvas/Roads/%s/Light", nextPos) , self.MapObject)
            -- local roadLightAni = roadLight and roadLight:GetComponent("Animator")
            if roadLight then
                roadLight:SetActive(true)
                self:once(1, function ()
                    roadLight:SetActive(false)
                end)
            end
            self:checkAngle()
            Game:playSound("sound_sugoroku_move")
        end)
    end
    moveTween:ease(DT.Ease.Linear)
        :link()
        :onComplete(function()
            if self._isClosing then
                return
            end
            self._isMoving = false
            self._isRolling = false
            if self._pendingItemChangeCheck then
                self._pendingItemChangeCheck = false
                self:checkItemChangeMultip()
            end
            if mapLightTween.act and mapLightTween.act:IsActive() then
                mapLightTween:kill()
            end
            mapLightGroup.alpha = 1
            self:setMapLightFrame(self.curPos)
            self:getMapReward(multiple)
        end)
    -- mapLightFrameTween:ease(DT.Ease.Linear):link()
end

function P:checkAngle()
    local angle = (self.curPos >= self.changeAngle[2][1] or self.curPos < self.changeAngle[1][1]) and 0 or 1
    self.Role.transform.localPosition = bee.v3(angle == 0 and 14 or -14, self.Role.transform.localPosition.y, 0)
    self.Role.transform.localEulerAngles = bee.v3(0, angle * 180, 0)
end

--设置地图选中框
function P:setMapLightFrame(pos)
    pos = pos or MonopolyModel.curPos
    local point = self:find("Canvas/Roads/" .. pos, self.MapObject)
    if bee.isNull(point) then
        return
    end
    self.MapLightFrame.transform.localPosition = point.transform.localPosition + bee.v3(-1, 21, 0)
end

--获得地图奖励表现
function P:getMapReward(multiple)
    local cfg = self.MapRewardCfg[self.curPos]
    if cfg.rewards == nil then
        return
    end
    self.RoleGetTip:SetActive(true)
    local propCfg = tpl_props[cfg.rewards[1]]
    bee.setIcon(self.RoleGetTipIcon, propCfg.icon)
    bee.setText(self.RoleGetTipValue, "+" .. _N2(cfg.rewards[2] * multiple))
    Game:playSound("sound_sugoroku_reward")

    if cfg.quality >= 5 then
        self.RoleGetFx:SetActive(true)
        Game:playSound("sound_sugoroku_prize")
    end
    
    CU.Canvas.ForceUpdateCanvases()
    CU.UI.LayoutRebuilder.ForceRebuildLayoutImmediate(self.RoleGetTip:GetComponent("RectTransform"))

    self:once(2, function ()
        self.RoleGetTip:SetActive(false)
        self.RoleGetFx:SetActive(false)
    end)
end

--刷新奖励进度
function P:evt_MonopolyProgressReward()
    if self._isClosing then
        return
    end

    -- self:refreshDiceCount()
    local rewards = {}
    for _,v in pairs(self.RewardItemList) do
        if v.getable then
            local id = v.cfg.rewards[1]
            local num = v.cfg.rewards[2]
            if rewards[id] == nil then
                rewards[id] = 0
            end
            rewards[id] = rewards[id] + num
        end
    end
    local items = {}
    for k,v in pairs(rewards) do
        table.insert(items, {id = k, num = v})
    end
    UiManager:showUI("BackpackClaimResult", {items = items})

    self:refreshProgress()
end

--刷新骰子数量
function P:refreshDiceCount()
    local count = MonopolyModel:getItemCount()
    bee.setText(self.AmountValue, count)
end

--刷新奖励进度
function P:refreshProgress()
    local totalConsume = MonopolyModel.totalConsume or 0
    local progressWidth = 0
    local previousQuantity = 0
    local rewardCount = #self.RewardCfgList
    local curProgressIndex = 0

    bee.setText(self.CurProgressValue, totalConsume)

    for i, rewardCfg in ipairs(self.RewardCfgList) do
        local stageWidth = i == 1 and 173 or (i == rewardCount and 120 or 108)
        local quantity = rewardCfg.quantity
        local stageQuantity = quantity - previousQuantity

        if totalConsume >= quantity then
            progressWidth = progressWidth + stageWidth
            curProgressIndex = i
        elseif totalConsume > previousQuantity and stageQuantity > 0 then
            progressWidth = progressWidth + stageWidth * (totalConsume - previousQuantity) / stageQuantity
            break
        else
            break
        end

        previousQuantity = quantity
    end

    local progressTransform = self.Progress.transform
    progressTransform.sizeDelta = bee.v2(progressWidth, progressTransform.sizeDelta.y)

    for k,v in pairs(self.RewardItemList) do
        if MonopolyModel.rewardProgress >= k then
            v.getable = false
            v.mask:SetActive(true)
            v.lock:SetActive(false)
            v.geted:SetActive(true)
        else
            if curProgressIndex >= k then
                v.getable = true
                v.mask:SetActive(false)
                v.lock:SetActive(false)
                v.geted:SetActive(false)
            else
                v.getable = false
                v.mask:SetActive(true)
                v.lock:SetActive(true)
                v.geted:SetActive(false)
            end
        end
        v.reddot:SetActive(v.getable)
    end
    MonopolyModel:refreshReddot()
end

--设置倍率
function P:refreshMultip(change)
    AnimationMgr:playAnimator(self.MultipleButtonAni, "UI_1_MultipleButton")
    bee.setText(self.MultipleText, "x" .. MonopolyModel.multiple)
    if change then
        Game:playSound("ui_bubble")
        for _,v in pairs(self.MapRewardItems) do
            local valueNode = v.value
            local valueText = _N2(v.cfg.rewards[2] * MonopolyModel.multiple)
            bee.Tween.killByTarget(valueNode)
            bee.tween(valueNode)
                :to(0.2, {scaleX = 0})
                :call(function()
                    bee.setText(valueNode, valueText)
                end)
                :to(0.2, {scaleX = 1})
                :link()
        end
    end
end
--切换倍率
function P:exchangeMultip()
    MonopolyModel:exchangeMultip()
    self:refreshMultip(true)
    self:checkExchangeMultip()
    bee.logEvent("monopoly-multiple", MonopolyModel.multiple)
end
--提示切换倍率
function P:checkExchangeMultip()
    local tip = MonopolyModel:checkMultipTip()
    if tip == nil then
        self.NumTips:SetActive(false)
        return
    end
    self.NumTips:SetActive(true)
end

--物品变动
function P:evt_ItemChangeRSP(msg)
    if self._isClosing then
        return
    end

    local activityItemIdChange = false
    for _,v in pairs(msg.item_list) do
        if v.item_id == MonopolyModel.activityItemId then
            activityItemIdChange = true
            break
        end
    end
    if not activityItemIdChange then
        return
    end

    --刷新骰子显示
    self:refreshDiceCount()
    if self._isRolling or self._isMoving or MonopolyModel.ctrling then
        self._pendingItemChangeCheck = true
        return
    end
    self:checkItemChangeMultip()
end

function P:evt_MonopolyPlayFail()
    self._isRolling = false
    if self._pendingItemChangeCheck then
        self._pendingItemChangeCheck = false
        self:checkItemChangeMultip()
    end
end

function P:checkItemChangeMultip()
    if self._isClosing then
        return
    end

    --自动降档
    local jumpGears = MonopolyModel:checkDownGearsMultip()
    if jumpGears then
        self:refreshMultip(true)
    end
    --换档提示
    self:checkExchangeMultip()
    --最小档位
    local inMin = MonopolyModel:switchMultipleBtn()
    self.MultipleButton:SetActive(not inMin)
end

--倒计时
function P:cutDown()
    if self.cutDownTag then
        scheduler:removeTag(self.cutDownTag)
        self.cutDownTag = nil
    end

    -- local activityId = MonopolyModel:getAcitvityId()
    -- local activityCfg = tpl_monopoly_activity[activityId]
    -- if not activityCfg or not activityCfg.time_end then
    --     return
    -- end

    local endTime = MonopolyModel:getActivityEndTime()
    if endTime <= 0 then
        return
    end

    local function refreshTime()
        local leftTime = math.max(0, endTime - bee.getServerTime())
        if leftTime > 3600 then
            bee.setText(self.Time, _F("LAB_MONOPOLY_ACTIVITY1_2", ShopModel:getShopTimeText(leftTime)))
        else
            bee.setText(self.Time, _F("LAB_MONOPOLY_ACTIVITY1_2", ShopModel:getShopTimeText2(leftTime)))
        end
        return leftTime > 0
    end

    if refreshTime() then
        self.cutDownTag = self:schedule(1, function()
            if not refreshTime() then
                scheduler:removeTag(self.cutDownTag)
                self.cutDownTag = nil
            end
        end)
    end
end

function P:releaseResources()
    self._isClosing = true
    self._isMoving = false
    self._isRolling = false
    self._pendingItemChangeCheck = false
    if not bee.isNull(self.RoleRoot) then
        bee.Tween.killByTarget(self.RoleRoot)
    end
    if self.cutDownTag then
        scheduler:removeTag(self.cutDownTag)
        self.cutDownTag = nil
    end
    self:releaseMap()
end

function P:onBtClose()
    if self._isClosing then
        return
    end
    self:hideUI(function()
        self._isClosing = true
        self:releaseResources()
    end)
end

function P:onHide()
    self:releaseResources()
end

function P:onDestroy()
    self:releaseResources()
    P.super.onDestroy(self)
end

return P