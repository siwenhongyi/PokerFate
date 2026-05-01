local P = class("ActivityMain", UiFullView)

local SubView = {
	[ActivityId.NewmanCheckin] = {view = "views/Activitynewman/ActivityNewmanCheckin"},
	[ActivityId.SevenSignIn] = {view = "views/Activity/ActivitySignIn"},
	[ActivityId.SocialMedia] = {view = "views/Activity/ActivitySocialMedia"},
	[ActivityId.LinkEmail] = {view = "views/Activity/ActivityLinkEmail"},
	[ActivityId.ActivitySignIn] = {
		[1] = {view = "views/Activitynewman/ActivityNewmanCheckin"},
		[2] = {view = "views/ActivityGalaSeasonCheckin/ActivityGalaSeasonCheckin"},	-- 礼服季
		[3] = {view = "views/ActivitySchoolCheckin/ActivitySchoolCheckin"},	-- 开学季
		[4] = {view = "views/ActivityBunnyGirlCheckin/ActivityBunnyGirlCheckin"},	-- 兔女郎
	}
}

function P:onAwake()
	self._openAnim, self._closeAnim = "UI_1_" .. "ActivitySignIn" .. "_into", "UI_1_" .. "ActivitySignIn" .. "_back"
	self.AnimRoot = self:find("AnimRoot")
	self.Center = self:find("Center", self.AnimRoot)
	self.Left = self:find("Left", self.AnimRoot)

	self.ToggleScrollView = self:find("ToggleScrollView", self.Left)
	self.TabToggle = self:find("TabToggle", self.Left)
	self.TabToggle:SetActive(false)

	self.BackButton = self:find("LeftTop/BackButton", self.AnimRoot)
	bee.addClick(self.BackButton, function()
		self:hideUI()
	end)
end

function P:onStart()
	if self._params and self._params.activityId then
		self._selectSideTab = self._params.activityId
		if self._params.activityId == ActivityId.SevenSignIn then
        	bee.logEvent("7daycheckin-view")
		end
	elseif self._params and self._params.jump then
		self._selectSideTab = self._params.jump.sub_page[1]
	end

	self:initToggleList()
	self:refreshToggle()
end

function P:initToggleList()
	self.tabtoggleList = UiListEx:create(self.ToggleScrollView)
	self.tabtoggleList:setCreateFunc(function()
		return CU.GameObject.Instantiate(self.TabToggle)
	end)
	self.tabtoggleList:setRefreshFunc(function(data, item)
		self:setTabToggle(item, data)
	end)
	self.tabtoggleList:setWidth(160)
	self.tabtoggleList:setSpacing(5)
end

function P:refreshToggle()
	self._showList = ActivityModel:getActShowList()

	if self._selectSideTab then
		local isIn = false
		for k,v in pairs(self._showList) do
			if v.event_id == self._selectSideTab then
				isIn = true
				break
			end
		end
		if not isIn then
			self._selectSideTab = nil
		end
	end

	if not self._selectSideTab then
		self._selectSideTab = self._showList[1].event_id
	end

	self.tabtoggleList:setDatas(self._showList)
	self:refreshTabToggle()
	self:refreshCenter()
end

function P:refreshTabToggle()
	for k, v in pairs(self.tabtoggleList:getDatas()) do
		if v.node then
			if v.data.event_id == self._selectSideTab then
				-- self:playToggleInto(v.node)
				self:find("Ani_root", v.node).transform.localPosition = bee.v3(25, 0, 0)
				self:find("Ani_root/On", v.node):SetActive(true)
				self:find("Ani_root/Off", v.node):SetActive(true)
			else
				-- self:playToggleIdle2(v.node)
				self:find("Ani_root", v.node).transform.localPosition = bee.v3(0, 0, 0)
				self:find("Ani_root/On", v.node):SetActive(false)
				self:find("Ani_root/Off", v.node):SetActive(true)
			end
		end
	end
end

function P:setTabToggle(item, data)
	local Ani_root = self:find("Ani_root", item)

	local ToggleIcon = self:find("ToggleIcon", Ani_root)
	local NameText = self:find("Mask/NameText", Ani_root)
	self:find("Mask/ImageCD", Ani_root):SetActive(data.type == ActivityType.TimeLimit)

	bee.setIconInAtlas(ToggleIcon, data.icon, true)
	bee.setText(NameText, _T(data.name))

	local RedPoint = self:find("RedPoint", Ani_root)
	RedManager:unbind(RedPoint)
	if data.event_id == ActivityId.NewmanCheckin then
		RedManager:bind(RedPoint, RedTag.ActivityNewmanCheckin)
	else
		RedPoint:SetActive(false)
	end

	bee.removeAllClick(item)
	bee.addClick(item, function()
		Game:playSound("ui_tab_switch_1")
		if self._selectSideTab == data.event_id then
			return
		end
		self._selectSideTab = data.event_id
		self:refreshTabToggle()
		self:refreshCenter()
		
		if data.event_id == ActivityId.SevenSignIn then
			bee.logEvent("7daycheckin-tag")
		end
	end)
end

function P:refreshCenter()
	local viewInfo
	if self._selectSideTab == ActivityId.ActivitySignIn then
		viewInfo = SubView[self._selectSideTab][ActivityNewmanCheckinModel:getCheckinId()]
	else
		viewInfo = SubView[self._selectSideTab]
	end
	if not viewInfo then
		return
	end

	if self._curSubView then
		CU.GameObject.Destroy(self._curSubView)
		self._curSubView = nil
	end

	self._curSubView = bee.createObj(viewInfo.view)
	self._curSubView.transform:SetParent(self.Center.transform, false)
	if viewInfo.pos then
		self._curSubView.transform.localPosition = viewInfo.pos
	else
		self._curSubView.transform.localPosition = bee.v3(0, 0, 0)
	end
	self._curSubView.transform.localScale = bee.v3(1, 1, 1)
	self._curSubViewCls = ObjectPool:getCls(self._curSubView)
end

function P:evt_activity_over(e)
    if e == ActivityId.NewmanCheckin then
		self:refreshToggle()
    end
end

return P