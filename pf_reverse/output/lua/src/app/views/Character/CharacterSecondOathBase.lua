local P = class("CharacterSecondOathSAYAKA", UiFullView)

function P:onAwake()
	local Center = self:find("AnimRoot/Center")

	self.ClaimButton = self:find("ClaimButton", Center)
	self.CloseButton = self:find("CloseButton", Center)
	self.TaskListObj = self:find("TaskList", Center)
	self.Item1 = self:find("Item1", self.TaskListObj)
	self.Item1:SetActive(false)
	self.Locked = self:find("Locked", Center)
	self.LockedText = self:find("Locked/LockedText", Center)
	self.Title = self:find("Title", Center)

	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
	bee.addClick(self.ClaimButton, function()
		self:onClickClaimButton()
	end)
end

function P:onStart()
	if self._params.jumpId then
		self._role = CharacterModel:getRoleData(self._params.jumpId)
	elseif self._params.role then
		self._role = self._params.role
	end
	
	self:initTaskList()
	CharacterModel:reqRoleTaskList(self._role.role_id)
end

function P:evt_updateCharacterTask()
	self:refreshCenter()
end

function P:refreshCenter()
	self._taskDatas = CharacterModel:getRoleTaskList(self._role.role_id)
	self.taskList:setDatas(self._taskDatas)

	if not self._role:isAwaken() then
		self.Locked:SetActive(true)
		bee.setText(self.LockedText, _F("LAB_CHAR_ST_1", _T(self._role.info.name)))
	else
		self.Locked:SetActive(false)
	end

	if not self._role.locked then
		local isComplete = true
		for k,v in pairs(self._taskDatas) do
			if v.status ~= TaskStatus.Completed then
				isComplete = false
				break
			end
		end
		self.ClaimButton:SetActive(isComplete)

		if CharacterModel:isRoleSecondAwakenNewRed(self._role.role_id) then
			CharacterModel:removeSecondAwakenNewRed(self._role.role_id)
		end
	else
		self.ClaimButton:SetActive(false)
	end

    local titleList = {}
    titleList["tw"] = self:find("tw", self.Title)
    titleList["en"] = self:find("en", self.Title)
    titleList["jp"] = self:find("jp", self.Title)
    titleList["zh"] = self:find("zh", self.Title)
    local showTitle
    local curLan = LanguageManager:getLanguage()
    for k, v in pairs(titleList) do
        if k == curLan then
            v:SetActive(true)
            showTitle = v
        else
            v:SetActive(false)
        end
    end
end

function P:onClickClaimButton()
	bee.logEvent("character-special-task-claim", self._role.role_id)
	CharacterModel:reqRecRoleTaskRw(self._role, function()
		self:hideUI()

		local params = {}
		params.major_type = GMajorType.ROLE_SKIN
		params.id = self._role.info.special_outfit
		params.voiceKey = "awaken2"
		params.isSpecial = true

		UiManager:showUI("GachaResultShow", {showList = {params}})
	end)
end

function P:initTaskList()
	self.taskList = UiListEx:create(self.TaskListObj)
	self.taskList:setCreateFunc(function()
		return CU.GameObject.Instantiate(self.Item1)
	end)
	self.taskList:setRefreshFunc(function(data, item, isInit, index)
		self:setTaskItem(item, data, isInit, index)
	end)
	self.taskList:setWidth(155)
end

function P:setTaskItem(item, data, isInit, index)
    local Ani_root = self:find("Ani_root", item)
	local TaskText = self:find("TaskText", Ani_root)
	local GoButton = self:find("GoButton", Ani_root)
	local TagClaimed = self:find("TagClaimed", Ani_root)

	if not data.current_value then
		data.current_value = 0
	end

    if isInit and index > 0 then
        self:once(0.1 * (index - 1), function()
            Ani_root:SetActive(true)
            self:playAnimator("UI_1_TaskView_item_into", Ani_root)
        end)
        Ani_root:SetActive(false)
    else
        Ani_root:SetActive(true)
        self:playAnimator("UI_1_TaskView_item_idle", Ani_root)
    end

	local cfg = tpl_character_task[data.task_id]
	if not cfg then
		return
	end

	-- 任务描述
	local showText = TaskModel:getTaskDesc(cfg, data)
	local curValue = data.current_value or 0
	local needValue = TaskModel:getNeedValue(data)
	if cfg.task_type == 313 or cfg.task_type == 111 then
		needValue = data.value[3]
	end
	if curValue < needValue then
		showText = showText .. "  (" .. "<color=#D76487>" .. _N(curValue) .. "</color>/" ..  _N(needValue) .. ")"
	else
		local cur = math.min(curValue, needValue)
		showText = showText .. "  (" .. _N(cur) .. "/" ..  _N(needValue) .. ")"
	end
	bee.setText(TaskText, showText)

	TagClaimed:SetActive(data.status == TaskStatus.Completed)
	GoButton:SetActive(data.status ~= TaskStatus.Completed)

	bee.removeAllClick(GoButton)
	bee.addClick(GoButton, function()
		Game:playSound("ui_button_confirm")
		-- 前往跳转
		if cfg.jump then
			if cfg.jump == 4001 then
				if self.characterCls then
					self.characterCls:stopVoice()
				end
				self:hideUI()
			else
				ItemModel:jumpView(cfg.jump)
			end
		end
	end)
end

return P