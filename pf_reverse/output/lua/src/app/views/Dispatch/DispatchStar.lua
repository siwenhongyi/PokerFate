-- 牌手星级提升弹窗
-- 显示星级提升带来的属性变化: 奖励加成、时间缩短、彩蛋概率提升
local P = class("DispatchStar", UiDialog)

function P:onAwake()
    local Center = self:find("AnimRoot/Center")

    -- 角色名
    self.TextName = self:find("TextName", Center)
    self.CharacterImage = self:find("CharacterImage", Center)

    -- 关闭按钮
    self.CloseButton = self:find("CloseButton", Center)

    -- 当前星级
    self.star = self:find("star", Center)
    self.star1 = self:find("star1", self.star)
    self.star2 = self:find("star2", self.star)
    self.dispatch_icon_star = self:find("dispatch_icon_star", self.star)
    self.dispatch_icon_star:SetActive(false)

    -- 属性列表
    local Item = self:find("Item", Center)
    self.Items = {
        self:find("Item1", Item),
        self:find("Item2", Item),
        self:find("Item3", Item),
    }

    -- 关闭按钮事件
    bee.addClick2(self:find("bg_dispatch_level_01", Center), function()
        self:hideUI()
    end)
    
    Game:playSound("ui_level_upgrade_lobby")
end

function P:onShow()
    local params = self._params or {}
    local role = params.role_id and CharacterModel:getRole(params.role_id) or CharacterModel:getUsingRole()

    bee.invoke(self.CharacterImage, "setSkin", role:getSkinData(), false, true)
    bee.invoke(self.CharacterImage, "setSkinRotate")

    bee.setText(self.TextName, role:getName())

    local r = DispatchModel:getRole(role.role_id)
    local curStar = r and r.role_star or 2
    local preStar = curStar - 1
    local d1, d2 = tpl_character_info[preStar], tpl_character_info[curStar]

    if d1 and d2 then
        bee.setText(self:find("Ani_root/TextBase", self.Items[1]), "" .. d1.base_reward_up / 100 .. "%")
        bee.setText(self:find("Ani_root/TextUp", self.Items[1]), "" .. d2.base_reward_up / 100 .. "%")
        bee.setText(self:find("Ani_root/TextBase", self.Items[2]), "" .. d1.time_reduce / 100 .. "%")
        bee.setText(self:find("Ani_root/TextUp", self.Items[2]), "" .. d2.time_reduce / 100 .. "%")
        bee.setText(self:find("Ani_root/TextBase", self.Items[3]), "" .. d1.reward_bonus / 100 .. "%")
        bee.setText(self:find("Ani_root/TextUp", self.Items[3]), "" .. d2.reward_bonus / 100 .. "%")

        self.Items[1]:SetActive(d1.base_reward_up ~= d2.base_reward_up)
        self.Items[2]:SetActive(d1.time_reduce ~= d2.time_reduce)
        self.Items[3]:SetActive(d1.reward_bonus ~= d2.reward_bonus)
    end
    
    for i = 1, preStar do
        local star = CU.GameObject.Instantiate(self.dispatch_icon_star, self.star1.transform, false)
        star:SetActive(true)
    end
    for i = 1, curStar do
        local star = CU.GameObject.Instantiate(self.dispatch_icon_star, self.star2.transform, false)
        star:SetActive(true)
    end
    
    local index = 1
    for k, v in ipairs(self.Items) do
        if v.activeSelf then
            v:SetActive(false)
            self:once(0.8 + (index - 1) * 0.2, function()
                v:SetActive(true)
                
                self:playAnimator("UI_1_DispatchStar_item", self:find("Ani_root", v))
            end)
            index = index + 1
        end
    end
end


return P