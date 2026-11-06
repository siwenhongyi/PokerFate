-- 派遣历史记录详情提示
local P = class("DispatchSideRecordTips", UiBase)

function P:onAwake()
    local RecordTips = self:find("AnimRoot/Left/Record/RecordTips")

    -- 箭头图标
    self.dispatch_side_record_tips_bg_00 = self:find("dispatch_side_record_tips_bg_00", RecordTips)

    -- 角色列表
    self.RecordTipsList = self:find("RecordTipsList", RecordTips)
    self.Item01 = self:find("Item01", self.RecordTipsList)
    self.Item01:SetActive(false)

    bee.addClick2(self:find("Mask"), function()
        self:hideUI()
    end)

    -- 初始化角色列表
    self.RoleList = UiListEx:create(self.RecordTipsList)
    self.RoleList:setWidth(443)
    self.RoleList:setCreateFunc(function()
        return CU.GameObject.Instantiate(self.Item01)
    end)
    self.RoleList:setRefreshFunc(function(data, item)
        self:setRoleItem(data, item)
    end)
end

function P:onShow()
    local params = self._params or {}
    local data = params.data
    local target = params.target

    -- 角色列表
    local roles = data.roles or {}
    self.RoleList:setDatas(roles)

    -- 定位箭头指向目标元素
    self:updateArrowPosition(target)
end

function P:setRoleItem(data, item)
    local roleId = data.role_id

    -- 角色头像
    local role = CharacterModel:getRole(roleId)
    local Information = self:find("Information", item)
    if role then
        -- 角色名字
        bee.setText(self:find("TextName", Information), role:getName())
        -- 头像
        local skinCfg = role:getSkinData()
        bee.setIconInAtlas(self:find("Avatar/Mask/ImageIcon", item), tpl_props[skinCfg.avatar].icon)
    else
        local d = tpl_character[data.role_id]
        if d then
            bee.setText(self:find("TextName", Information), _T(d.name))
        end
    end

    -- 阵营图标
    local campCfg = tpl_camp_detail[data.camp_id]
    if campCfg then
        bee.setIconInAtlas(self:find("CampIcon/dispatch_main_camp_0", Information), campCfg.camp_icon)
    end

    -- 星级显示
    for i = 1, 5 do
        self:find("Star/dispatch_icon_star_" .. i, Information):SetActive(data.role_star >= i)
    end

    local Buff = self:find("Buff", Information)
    self:find("Easteregg", Buff):SetActive(data.base_bonus > 0)
    if data.base_bonus > 0 then
        bee.setText(self:find("Easteregg/Text", Buff), "" .. data.base_bonus / 100 .. "%")
    end
    self:find("Award", Buff):SetActive(data.base_reward_up > 0)
    if data.base_reward_up > 0 then
        bee.setText(self:find("Award/Text", Buff), "" .. data.base_reward_up / 100 .. "%")
    end
    self:find("Decelerate", Buff):SetActive(data.time_reduce < 0)
    if data.time_reduce < 0 then
        bee.setText(self:find("Decelerate/Text", Buff), "" .. data.time_reduce / 100 .. "%")
    end
    self:find("Accelerate", Buff):SetActive(data.time_reduce > 0)
    if data.time_reduce > 0 then
        bee.setText(self:find("Accelerate/Text", Buff), "" .. data.time_reduce / 100 .. "%")
    end

    scheduler:removeTarget(item)
    if 1 == data.status then
        local TextTime = self:find("Time/TextTime", item)
        TextTime:SetActive(true)
        self:find("Time/Completed", item):SetActive(false)
        self:find("Time/Dispatchtime", item):SetActive(true)

        local dt = data.end_ts - bee.getServerTime()
        if dt < 0 then dt = 0 end
        bee.setText(TextTime, TimeHelp:getTimeStr(dt))
        bee.schedule(1, function()
            local dt = data.end_ts - bee.getServerTime()
            if dt < 0 then dt = 0 end
            bee.setText(TextTime, TimeHelp:getTimeStr(dt))
        end, item)
    else
        self:find("Time/TextTime", item):SetActive(false)
        self:find("Time/Dispatchtime", item):SetActive(false)
        self:find("Time/Completed", item):SetActive(true)
    end
    
    local Content = self:find("Award/Items/Viewport/Content", item)
    self:removeAllChildren(Content)
    local Item01 = self:find("Award/Item01", item)
    Item01:SetActive(false)

    -- 收集奖励数据
    local rewards = {}

    -- 额外奖励
    if 1 == data.status or 2 == data.status then
        local rewards, rate = DispatchModel:getEggReward(data)
        if rewards then
            local Item = CU.GameObject.Instantiate(Item01, Content.transform, false)
            Item:SetActive(true)
            PropItem:create(Item, {item_id = GPropId.DispatchBonus, num = 0})
            self:find("Easteregg", Item):SetActive(true)
            if rate and rate > 0 then
                bee.setText(self:find("Easteregg/TextRate", Item), rate / 100 .. "%")
            end
            bee.addClick(Item, function()
		        Game:playSound("ui_button_confirm")
                local rewardsBonus = {}
                for i = 1, #rewards, 3 do
                    table.insert(rewardsBonus, {item_id = rewards[i], num = rewards[i + 1], weight = rewards[i + 2]})
                end
                UiManager:showUI("DispatchRewardBondTip", {items = rewardsBonus, target = Item})
            end, true)
        end
    else
        if data.reward_bonus then
            for i = 1, #data.reward_bonus - 1, 2 do
                table.insert(rewards, {item_id = data.reward_bonus[i], num = data.reward_bonus[i + 1], is_egg = true})
            end
        end
    end

    if data.exp and data.exp > 0 then
        table.insert(rewards, {item_id = GPropId.ExpDispatch, num = data.exp, format = {VipModel:getFriendshipDispatch()}})
    end
    if data.bond and data.bond > 0 then
        table.insert(rewards, {item_id = GPropId.BondDispatch, num = data.bond, format = {VipModel:getFriendshipDispatch()}})
    end
    if data.star_exp and data.star_exp > 0 then
        table.insert(rewards, {item_id = GPropId.RoleDispatchExp, num = data.star_exp})
    end
    if data.camp_quality and data.camp_quality > 0 then
        table.insert(rewards, {item_id = GPropId.CampDispatchUpgrade, num = data.camp_quality})
    end

    for _, v in ipairs(rewards) do
        local Item = CU.GameObject.Instantiate(Item01, Content.transform, false)
        Item:SetActive(true)
        PropItem:create(Item, v): bindTips()
        self:find("Easteregg", Item):SetActive(v.is_egg)
    end
end

function P:updateArrowPosition(target)
    if not target or not self.dispatch_side_record_tips_bg_00 then
        return
    end

    local pos = target.transform.position
    local pos2 = self.dispatch_side_record_tips_bg_00.transform.position
    pos2.y = pos.y
    self.dispatch_side_record_tips_bg_00.transform.position = pos2
end

return P