local P = class("SpringFestivalRules", UiDialog)

function P:onAwake()
    local Center = self:find("AnimRoot/Center")
    self.BackButton = self:find("spring_btn_tc_close", Center)
    self.ScrollContent = self:find("springfestivalList/Viewport/Content", Center):GetComponent("RectTransform")
    self.RuleText = self:find("Rules", self.ScrollContent)
    self.ItemRoot = self:find("Items", self.ScrollContent)
    self.Item = self:find("springfestivalList/Item1", Center)

    bee.addClick(self.BackButton, function()
		Game:playSound("ui_button_confirm")
		self:hideUI()
	end)

    self.IconDic = {
        [1] = {iconIndex = 3, lab = "LAB_FESTIVAL_ACTIVITY1_3"},
        [2] = {iconIndex = 2, lab = "LAB_FESTIVAL_ACTIVITY1_4"},
        [3] = {iconIndex = 1, lab = "LAB_FESTIVAL_ACTIVITY1_5"},
    }

    bee.logEvent("springfestival-rules")
end

function P:onStart()
    self:showPropItem()
end

function P:showPropItem()
    local list = {}
    for _,v in pairs(tpl_festival_pool) do
        table.insert(list, v)
    end
    table.sort(list, function(a, b) return a.index < b.index end)
    for _,v in pairs(list) do
        local item = CU.GameObject.Instantiate(self.Item, self.ItemRoot.transform, false)
        item:SetActive(true)
        local data = {id = v.rewards[1], num = v.rewards[2]}
        PropItem:create(item, data):bindTips()
        self:find("RareFrame", item):SetActive(v.is_publicity ~= nil)
        if v.is_publicity then
            local rareIcon = self:find("RareFrame", item)
            local rareText = self:find("RareFrame/Rare", item)
            bee.setIcon(rareIcon, string.format("Spring[spring_btn_tc_labe_0%s]", self.IconDic[v.rarity].iconIndex))
            bee.setText(rareText, _T(self.IconDic[v.rarity].lab))
        end
    end
end

