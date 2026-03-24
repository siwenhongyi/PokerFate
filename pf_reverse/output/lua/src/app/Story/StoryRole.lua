local P = class("StoryRole", Object)

function P:ctor(id, node, data)
    self.roleId = id
    self.node = node
    self.data = data
end

