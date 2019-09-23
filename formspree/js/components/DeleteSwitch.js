/** @format */

const React = require('react') // eslint-disable-line no-unused-vars
import LoaderButton from './LoaderButton'

export default class DeleteSwitch extends React.Component {
  constructor(props) {
    super(props)

    this.delete = this.delete.bind(this)
    this.cancelDelete = this.cancelDelete.bind(this)

    this.state = {
      deleting: false
    }
  }

  render() {
    const {
      label = 'Delete',
      description,
      warningTitle,
      warningMessage,
      narrow
    } = this.props
    if (this.state.deleting) {
      return (
        <>
          <div className="switch">
            {warningTitle ? (
              <h4>{warningTitle}</h4>
            ) : (
              <h4>Are you sure you want to delete?</h4>
            )}
          </div>
          <div className="row">
            <div className={narrow ? '' : 'col-2-3'}>{warningMessage}</div>
            <div className={narrow ? 'row spacer' : 'col-1-3 right'}>
              <button
                onClick={this.cancelDelete}
                className="deemphasize"
                style={{marginRight: '5px'}}
              >
                Cancel
              </button>
              <LoaderButton onClick={this.delete}>{label}</LoaderButton>
            </div>
          </div>
        </>
      )
    } else {
      return (
        <>
          <div className="switch">
            <div className="switch-container">
              <a onClick={this.delete} href="#">
                <i className="fa fa-trash-o delete" />
              </a>
            </div>
            <div className="switch-label">{this.props.children}</div>
          </div>
          <div className="switch-description">{description}</div>
        </>
      )
    }
  }

  cancelDelete(e) {
    e.preventDefault()
    this.setState({deleting: false})
    this.props.onDeletingChanged && this.props.onDeletingChanged(false)
  }

  async delete(e) {
    e.preventDefault()

    if (!this.state.deleting) {
      // double-check the user intentions to delete,
      this.setState({deleting: true})
      this.props.onDeletingChanged && this.props.onDeletingChanged(true)
      return
    }

    this.props.onDelete && this.props.onDelete()
  }
}
